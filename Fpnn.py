# coding: utf-8
from __future__ import with_statement

import time
import struct
import threading
import hashlib
import socket
import msgpack
import Queue

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography import utils
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

__all__ = ('FpnnCallback', 'FpnnConnectedCallback', 'FpnnConnectionWillCloseCallback', 'TCPClient')

FPNN_PYTHON_VERSION = 1
FPNN_FLAG_MSGPACK = 0x80
FPNN_MT_ONEWAY = 0
FPNN_MT_TWOWAY = 1
FPNN_MT_ANSWER = 2

class FpnnCallback:
    timeoutSecond = 0
    createTime = 0
    
    def callback(self, answer, exception):
        pass

class FpnnConnectedCallback:
    def callback(self):
        pass

class FpnnConnectionWillCloseCallback:
    def callback(self, causedByError):
        pass

class Header(object):

    def __init__(self, magic, version, flag, mtype, ss, psize):
        self.magic = magic
        self.version = version
        self.flag = flag
        self.mtype = mtype
        self.ss = ss
        self.psize = psize

    def pack(self):
        return struct.pack('<4sBBBBI',
                           self.magic,
                           self.version,
                           self.flag,
                           self.mtype,
                           self.ss,
                           self.psize)

class Quest(object):

    nextSeq = 0

    def __init__(self, method, params, oneway = False):
        self.header = Header("FPNN", FPNN_PYTHON_VERSION, 0, 0, 0, 0)
        self.header.flag = FPNN_FLAG_MSGPACK
        self.header.mtype = FPNN_MT_ONEWAY if oneway else FPNN_MT_TWOWAY
        self.header.ss = len(method)
        if not oneway:
            self.seqNum = self.nextSeqNum()
        self.method = method
        self.payload = msgpack.packb(params)
        self.header.psize = len(self.payload)

    @classmethod
    def nextSeqNum(cls):
        if cls.nextSeq >= 2147483647:
            cls.nextSeq = 0
        cls.nextSeq += 1
        return cls.nextSeq

    def raw(self):
        packet = self.header.pack()
        if self.header.mtype == FPNN_MT_TWOWAY:
            packet += struct.pack('<I', self.seqNum)
        packet += struct.pack('!%ds%ds' % (len(self.method), len(self.payload)),
                              self.method,
                              self.payload)
        return packet

class AsyncCallback(object):
    def __init__(self, cb, answer, exception):
        self.cb = cb
        self.answer = answer
        self.exception = exception

class TCPClient(object):

    def __init__(self, ip, port, autoReconnect = True, timeout=5):
        self.socket = None
        self.timeout = timeout
        self.stop = False
        self.isEncryptor = False
        self.canEncryptor = True
        self.ip = ip
        self.port = port
        self.socket = None
        self.sockLock = threading.Lock()
        self.cbDict = {}
        self.dictLock = threading.Lock()
        self.rThread = None
        self.cTimer = None
        self.connectCb = None
        self.closeCb = None
        self.asyncCallbackQueue = Queue.Queue(maxsize = 0)
        self.asyncCallbackQueueLock = threading.Lock()
        self.asyncCallbackThreadPool = []
        self.autoReconnect = autoReconnect
        self.startAsyncCallbackThread()
        self.startCheckTimeoutTimer()

    def __del__(self):
        self.stop = True
        if self.rThread != None:
            self.rThread.join()
        if self.cTimer != None:
            self.cTimer.cancel()
        for t in self.asyncCallbackThreadPool:
            t.join()

    def setConnectionConnectedCallback(self, cb):
        self.connectCb = cb

    def setConnectionWillCloseCallback(self, cb):
        self.closeCb = cb

    def startReceiveThread(self):
        if self.rThread == None:
            self.rThread = threading.Thread(target=TCPClient.receiveThread, args=(self,))
            self.rThread.setDaemon(True)
            self.rThread.start()

    def startAsyncCallbackThread(self):
        for i in range(0, 3):
            t = threading.Thread(target=TCPClient.callAsyncCallback, args=(self,))
            t.setDaemon(True)
            t.start()
            self.asyncCallbackThreadPool.append(t)

    def startCheckTimeoutTimer(self):
        if self.cTimer == None:
            self.cTimer = threading.Timer(1, self.timeoutChecker)
            self.cTimer.start()

    def reconnect(self):
        with self.sockLock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
            self.socket.settimeout(0.5)
            self.startReceiveThread()
            if self.connectCb != None:
                self.connectCb.callback()

    def connect(self):
        self.reconnect()
    
    def close(self):
        self.stop = True
        with self.sockLock:
            if self.socket:
                self.socket.close()
        if self.rThread != None:
            self.rThread.join()
            self.rThread = None
        if self.cTimer != None:
            self.cTimer.cancel()
            self.cTimer = None
        for t in self.asyncCallbackThreadPool:
            t.join()
        self.asyncCallbackThreadPool = []

    def putCb(self, seqNum, cb):
        with self.dictLock:
            self.cbDict[seqNum] = cb 

    def getCb(self, seqNum):
        cb = None
        with self.dictLock:
            cb = self.cbDict.pop(seqNum, None)
            return cb

    def timeoutChecker(self):
        timeoutList = []
        with self.dictLock:
            for seqNum in self.cbDict:
                if self.isCallbackTimeout(self.cbDict[seqNum]):
                    timeoutList.append(seqNum)
        for seqNum in timeoutList:
            cb = self.getCb(seqNum)
            if cb != None:
                self.invokeCallback(cb, None, Exception("Quest timeout"))
         
        self.cTimer = threading.Timer(1, self.timeoutChecker)
        self.cTimer.start()

    def isCallbackTimeout(self, cb):
        timeoutValue = self.timeout
        if cb.timeoutSecond > 0:
            timeoutValue = cb.timeoutSecond
        if timeoutValue > 0:
            now = int(time.time())
            return now - cb.createTime >= timeoutValue
        return False

    def enableEncryptor(self, peerPubData, curveName = 'secp256k1', strength = 128):
        if not self.canEncryptor:
            raise Exception("can not enable encryptor after a quest is sended")

        if curveName not in ['secp256k1', 'secp256r1', 'secp192r1', 'secp224r1']:
            curveName = 'secp256k1'

        curve = ec.SECP256K1()
        if curveName == 'secp256k1':
            curve = ec.SECP256K1()
        elif curveName == 'secp256r1':
            curve = ec.SECP256R1()
        elif curveName == 'secp192r1':
            curve = ec.SECP192R1()
        else:
            curve = ec.SECP224R1()

        if strength not in [128, 256]:
            strength = 128
        self.strength = strength
        
        priKey = ec.generate_private_key(curve, default_backend())
        pubKey = priKey.public_key()
        peerPubKey = load_pem_public_key(peerPubData, backend=default_backend()) 

        secret = priKey.exchange(ec.ECDH(), peerPubKey)

        self.iv = hashlib.md5(secret).digest()
        if strength == 128:
            self.key = secret[0:16]
        else:
            if len(secret) == 32:
                self.key = secret
            else:
                self.key = hashlib.sha256(secret).digest()

        self.isEncryptor = True
        self.canEncryptor = False

        sendPubKey = utils.int_to_bytes(pubKey.public_numbers().x, 32) + utils.int_to_bytes(pubKey.public_numbers().y, 32)
        self.sendQuest("*key", {"publicKey" : sendPubKey, "streamMode" : False, "bits" : self.strength})

    def encrypt(self, buffer, isEncrypt):
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(self.iv), backend = default_backend())
        if isEncrypt:
            encryptor = cipher.encryptor()
            return encryptor.update(buffer) + encryptor.finalize()
        else:
            decryptor = cipher.decryptor()
            return decryptor.update(buffer) + decryptor.finalize()

    def sendAll(self, buffer):
        with self.sockLock:
	        self.socket.sendall(buffer)

    def recvAll(self, data_len):
        buffer = b''
        while True:
            try:
                recv_bytes = self.socket.recv(data_len)
            except socket.timeout, e:
                if self.stop:
                    raise Exception("connect close")
                continue
            except Exception, e:
                raise Exception("connect close")

            if recv_bytes == '':
                raise Exception("socket connection broken")
            
            buffer += recv_bytes
            if len(buffer) >= data_len:
                break
        return buffer 

    def callAsyncCallback(self):
        while (not self.stop):
            ac = None
            try:
                ac = self.asyncCallbackQueue.get(False)
            except Exception, e:
                if self.stop:
                    break
                else:
                    time.sleep(0.2)
                    continue

            ac.cb.callback(ac.answer, ac.exception)

    def receiveThread(self):
        while (not self.stop):
            try:
                arr = []
                buffer = None
                if self.isEncryptor:
                    buffer = self.recvAll(4)
                    arr = struct.unpack('<I', buffer)
                    buffer = self.recvAll(arr[0])
                    buffer = self.encrypt(buffer, False)
                    arr = struct.unpack('<4sBBBBII' + str(arr[0] - 16) + 's', buffer)
                else:
                    buffer = self.recvAll(16)
                    arr = struct.unpack('<4sBBBBII', buffer)

                seqNum = arr[6] 
                payload = ''
                if self.isEncryptor:
                    payload = arr[7]
                else:
                    payload = self.recvAll(arr[5])
                
                answer = msgpack.unpackb(payload)

                cb = self.getCb(seqNum)
                
                self.invokeCallback(cb, answer, None)

            except Exception, e:
                try:
                    if self.closeCb != None:
                        self.closeCb.callback(self.stop == False)

                    if self.stop:
                        break

                    if self.autoReconnect:
                        self.reconnect()
                    else:
                        break
                except:
                    break

        self.exceptionFlushAll()
        self.rThread = None            

    def sendQuest(self, method, params, cb = None, timeout = 0):
        if cb != None:
            cb.syncSemaphore = None
            cb.syncAnswer = None
            cb.syncException = None
            cb.timeoutSecond = timeout
            cb.createTime = int(time.time()) 

        self.send(method, params, cb)

    def sendQuestSync(self, method, params, timeout = 0):
        cb = FpnnCallback()
        cb.syncSemaphore = threading.Semaphore(0)
        cb.syncAnswer = None
        cb.syncException = None
        cb.timeoutSecond = timeout
        cb.createTime = int(time.time())
        self.send(method, params, cb)
        
        cb.syncSemaphore.acquire()
      
        if cb.syncException == None:
            return cb.syncAnswer
        else:
            raise cb.syncException

    def send(self, method, params, cb = None):
        try:
            oneway = (method != "*key" and cb == None)

            quest = Quest(method, params, oneway)

            if self.socket is None:
                self.reconnect()
            
            buffer = quest.raw()

            if self.isEncryptor and method != "*key":
                encryptBuffer = self.encrypt(buffer, True)
                buffer = struct.pack('<I' + str(len(buffer)) + 's', len(buffer), encryptBuffer)

            self.sendAll(buffer)

            self.canEncryptor = False

            if oneway or cb == None:
                return
           
            self.putCb(quest.seqNum, cb)

        except Exception, e:
            if self.autoReconnect:
                try:
                    self.reconnect()
                except Exception, e:
                    pass
            self.invokeCallback(cb, None, e)

    def invokeCallback(self, cb, answer, exception):
        if cb != None:
            if cb.syncSemaphore == None:
                with self.asyncCallbackQueueLock:
                    self.asyncCallbackQueue.put(AsyncCallback(cb, answer, exception))
            else:
                cb.syncAnswer = answer 
                cb.syncException = exception 
                cb.syncSemaphore.release()

    def exceptionFlushAll(self):
        with self.dictLock:
            removeList = []
            for seqNum in self.cbDict:
                cb = self.cbDict[seqNum]
                removeList.append(seqNum)
                self.invokeCallback(cb, None, Exception("connection was broken"))
            for seqNum in removeList:
                self.cbDict.pop(seqNum, None)

