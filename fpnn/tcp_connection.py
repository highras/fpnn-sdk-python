#encoding=utf8

import time
import errno
import threading
import struct
import socket
import msgpack
from enum import Enum
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from .quest import *
from .tcp_client import *
from .fpnn_error import *

class ReadPackageStep(Enum):
    READ_HEADER_NO_ENCRYPTOR = 1
    READ_LEFT_NO_ENCRYPTOR = 2
    READ_HEADER_ENCRYPTOR = 3
    READ_LEFT_ENCRYPTOR = 4

class ReadPackage(object):
    def __init__(self):
         self.reset()
    
    def reset(self):
        self.mtype = None
        self.ss = None
        self.sequnce_num = None
        self.method = None
        self.psize = None
        self.payload = None

class FpnnQuestCallback(object):
    def __init__(self, callback, timeout):
        self.callback = callback
        self.timeout = timeout
        self.create_time = int(round(time.time() * 1000))
        self.sync_semaphore = None
        self.sync_answer = None

class ProcessorConnectionInfo(object):
    def __init__(self, tcp_connection, quest):
        self.connection = tcp_connection
        self.quest = quest
        self.is_answer = False

    def get_connection_id(self):
        return self.connection.connection_id

    def send_answer(self, answer):
        answer.sequnce_num = self.quest.sequnce_num
        self.connection.send_answer(answer)

class TCPConnectionInfo(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.encrypted = False
        self.encrypted_key = None
        self.encrypted_iv = None

class TCPConnection(object):
    next_id = 0
    def __init__(self, client, engine, info, sock):
        self.connection_id = self.get_id()
        self.engine = engine
        self.client = client
        self.connection_info = info
        self.socket = sock
        self.write_lock = threading.Lock()
        self.out_queue = []
        self.in_buffer = bytearray(0)
        self.callback_map = {}
        self.callback_lock = threading.Lock()
        self.processor = None
        self.connection_callback = None
        self.need_read_lenth = 12
        self.read_step = ReadPackageStep.READ_HEADER_NO_ENCRYPTOR
        if self.connection_info.encrypted:
            self.need_read_lenth = 4
            self.read_step = ReadPackageStep.READ_HEADER_ENCRYPTOR
        self.read_package = ReadPackage()

    def __del__(self):
        self.socket.close()

    @classmethod
    def get_id(cls):
        cls.next_id += 1
        return cls.next_id

    def encrypt(self, buffer, is_encrypt):
        cipher = Cipher(algorithms.AES(self.connection_info.encrypted_key), modes.CFB(self.connection_info.encrypted_iv), backend = default_backend())
        if is_encrypt:
            encryptor = cipher.encryptor()
            return encryptor.update(buffer) + encryptor.finalize()
        else:
            decryptor = cipher.decryptor()
            return decryptor.update(buffer) + decryptor.finalize()

    def send_quest(self, quest, callback, timeout):
        buffer = quest.raw()
        if self.connection_info.encrypted and quest.method != "*key":
            encrypt_buffer = self.encrypt(buffer, True)
            buffer = struct.pack('<I' + str(len(buffer)) + 's', len(buffer), encrypt_buffer)

        with self.callback_lock:
            self.callback_map[quest.sequnce_num] = callback

        with self.write_lock:
            try:
                self.out_queue.append(buffer)
                self.engine.require_write(self)
            except:
                pass
    
    def send_answer(self, answer):
        buffer = answer.raw()
        if self.connection_info.encrypted:
            encrypt_buffer = self.encrypt(buffer, True)
            buffer = struct.pack('<I' + str(len(buffer)) + 's', len(buffer), encrypt_buffer)
        
        with self.write_lock:
            try:
                self.out_queue.append(buffer)
                self.engine.require_write(self)
            except:
                pass

    def process_io(self, can_read, can_write):
        invalid = False
        if can_read:
            invalid = self.read()

        if (not invalid):
            invalid = self.write()

        if invalid:
            self.engine.quit_in_loop(self)
            self.clean_callback()
            if self.connection_callback != None:
                self.connection_callback.closed(self.connection_id, self.connection_info.host + ':' + str(self.connection_info.port), True)
            self.client.notice_closed()

    def clean_callback(self):
        answer = Answer()
        answer.sequnce_num = 0
        answer.set_error(FPNN_ERROR.FPNN_EC_CONNECTION_IS_CLOSE.value, 'connection is closed')
        with self.callback_lock:
            for (socket_fd, callback) in  self.callback_map.items(): 
                if callback != None:
                    if callback.sync_semaphore != None:
                        callback.sync_answer = answer
                        callback.sync_semaphore.release()
                    elif callback.callback != None:
                        self.engine.thread_pool.submit(callback.callback.callback, answer)
            self.callback_map.clear()

    def check_timeout(self):
        answer = Answer()
        answer.sequnce_num = 0
        answer.set_error(FPNN_ERROR.FPNN_EC_QUEST_TIMEOUT.value, 'quest timeout')
        now = int(round(time.time() * 1000))
        with self.callback_lock:
            del_callback_set = set()
            for (socket_fd, callback) in  self.callback_map.items():
                if callback != None:
                    if callback.timeout > 0 and now - callback.create_time >= callback.timeout:
                        if callback.sync_semaphore != None:
                            callback.sync_answer = answer
                            callback.sync_semaphore.release()
                        elif callback.callback != None:
                            self.engine.thread_pool.submit(callback.callback.callback, answer)
                        del_callback_set.add(socket_fd)
            for s in del_callback_set:
                del self.callback_map[s]

    def write(self):
        with self.write_lock:
            while len(self.out_queue) > 0:
                buffer = self.out_queue[0]
                while len(buffer) > 0:
                    send = 0
                    try:
                        send = self.socket.send(buffer)
                    except socket.error as error:
                        if error.errno == errno.EAGAIN or error.errno == errno.EWOULDBLOCK:
                            if send > 0:
                                buffer = buffer[send:]
                                self.out_queue[0] = buffer
                                return False
                        elif error.errno == errno.EINTR:
                            if send > 0:
                                buffer = buffer[send:]
                                continue
                        else:
                            return True
                    except:
                        return True

                    if send == len(buffer):
                        self.out_queue.pop(0)

                    buffer = buffer[send:]

            self.engine.release_write(self)
            return False

    def read(self):
        while True:
            buffer = None
            try:
                buffer = self.socket.recv(self.need_read_lenth)
                if len(buffer) == 0:
                    return True
            except socket.error as error:
                if error.errno == errno.EAGAIN or error.errno == errno.EWOULDBLOCK:
                    return False
                elif error.errno == errno.EINTR:
                    continue
                else:
                    return True
            except:
                return True

            if buffer != None and len(buffer) > 0:
                self.check_read_finish(buffer)

    def check_read_finish(self, buffer):
        for s in buffer:
            self.in_buffer.append(s)

        if len(buffer) < self.need_read_lenth:
            self.need_read_lenth -= len(buffer)
            return

        if self.read_step == ReadPackageStep.READ_HEADER_NO_ENCRYPTOR:
            arr = struct.unpack('<4sBBBBI', self.in_buffer)
            self.read_package.mtype = arr[3]
            self.read_package.ss = arr[4]
            self.read_package.psize = arr[5]
            self.read_step = ReadPackageStep.READ_LEFT_NO_ENCRYPTOR
            if self.read_package.mtype == FpnnMType.FPNN_MT_ONEWAY.value:
                self.need_read_lenth = self.read_package.ss + self.read_package.psize
            elif self.read_package.mtype == FpnnMType.FPNN_MT_TWOWAY.value:
                self.need_read_lenth = self.read_package.ss + self.read_package.psize + 4
            else:
                self.need_read_lenth = self.read_package.psize + 4
            self.in_buffer = bytearray(0)
            return
                
        if self.read_step == ReadPackageStep.READ_LEFT_NO_ENCRYPTOR:
            if self.read_package.mtype == FpnnMType.FPNN_MT_ONEWAY.value:
                arr = struct.unpack('<' + str(self.read_package.ss) + 's' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.method = arr[0]
                self.read_package.payload = arr[1]
            elif self.read_package.mtype == FpnnMType.FPNN_MT_TWOWAY.value:
                arr = struct.unpack('<I' + str(self.read_package.ss) + 's' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.sequnce_num = arr[0]
                self.read_package.method = arr[1]
                self.read_package.payload = arr[2]
            else:
                arr = struct.unpack('<I' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.sequnce_num = arr[0]
                self.read_package.payload = arr[1]

            self.read_step = ReadPackageStep.READ_HEADER_NO_ENCRYPTOR
            self.need_read_lenth = 12
            self.handle_package(self.read_package)
            self.read_package.reset()
            self.in_buffer = bytearray(0)
            return

        if self.read_step == ReadPackageStep.READ_HEADER_ENCRYPTOR:
            arr = struct.unpack('<I', self.in_buffer)
            self.read_step = ReadPackageStep.READ_LEFT_ENCRYPTOR
            self.need_read_lenth = arr[0]
            self.in_buffer = bytearray(0)
            return
        
        if self.read_step == ReadPackageStep.READ_LEFT_ENCRYPTOR:
            self.in_buffer = self.encrypt(self.in_buffer, False)
            buffer = self.in_buffer[0:12]
            arr = struct.unpack('<4sBBBBI', buffer)
            self.read_package.mtype = arr[3]
            self.read_package.ss = arr[4]
            self.read_package.psize = arr[5]
            self.in_buffer = self.in_buffer[12:]

            if self.read_package.mtype == FpnnMType.FPNN_MT_ONEWAY.value:
                arr = struct.unpack('<' + str(self.read_package.ss) + 's' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.method = arr[0]
                self.read_package.payload = arr[1]
            elif self.read_package.mtype == FpnnMType.FPNN_MT_TWOWAY.value:
                arr = struct.unpack('<I' + str(self.read_package.ss) + 's' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.sequnce_num = arr[0]
                self.read_package.method = arr[1]
                self.read_package.payload = arr[2]
            else:
                arr = struct.unpack('<I' + str(self.read_package.psize) + 's', self.in_buffer)
                self.read_package.sequnce_num = arr[0]
                self.read_package.payload = arr[1]

            self.read_step = ReadPackageStep.READ_HEADER_ENCRYPTOR
            self.need_read_lenth = 4
            self.handle_package(self.read_package)
            self.read_package.reset()
            self.in_buffer = bytearray(0)
            return

    def process_quest(self, obj, quest):
        processor_connection_info = ProcessorConnectionInfo(self, quest)
        answer = obj(processor_connection_info, quest)
        if not quest.oneway and answer != None:
            processor_connection_info.send_answer(answer)

    def unpack_fix_bin(self, payload):
        try:
            data = msgpack.unpackb(payload)
            return data
        except UnicodeDecodeError:
            data = msgpack.unpackb(payload, raw = True)
            fixBinData = {}
            for (key, value) in data.items():
                fixBinData[str(key, encoding = "utf8")] = value
            data = fixBinData
            return data

    def handle_package(self, package):
        if package.mtype == FpnnMType.FPNN_MT_ONEWAY.value:
            if self.processor == None:
                return
            if package.method == None or package.payload == None:
                return
            method = package.method.decode('utf-8')
            if not hasattr(self.processor, method):
                return
            quest = Quest(package.method, True)
            quest.sequnce_num = package.sequnce_num
            quest.params_map = self.unpack_fix_bin(package.payload)
            obj = getattr(self.processor, method)
            self.engine.thread_pool.submit(obj, ProcessorConnectionInfo(self, quest), quest)
        elif package.mtype == FpnnMType.FPNN_MT_TWOWAY.value:
            if self.processor == None:
                return
            if package.method == None or package.payload == None:
                return
            method = package.method.decode('utf-8')
            if not hasattr(self.processor, method):
                return
            quest = Quest(package.method)
            quest.sequnce_num = package.sequnce_num
            quest.params_map = self.unpack_fix_bin(package.payload)
            obj = getattr(self.processor, method)
            self.engine.thread_pool.submit(self.process_quest, obj, quest)
        elif package.mtype == FpnnMType.FPNN_MT_ANSWER.value:
            callback = None
            with self.callback_lock:
                callback = self.callback_map.get(package.sequnce_num, None)
                if callback != None:
                    del self.callback_map[package.sequnce_num]

            answer = Answer()
            answer.sequnce_num = package.sequnce_num
            data = self.unpack_fix_bin(package.payload)
            if package.ss == 0:
                answer.set_params(data)
            else:
                answer.set_error(data.get("code", FPNN_ERROR.FPNN_EC_UNKNOWN_ERROR.value), data.get("ex", "unknown error"))

            if callback != None:
                if callback.sync_semaphore != None:
                    callback.sync_answer = answer
                    callback.sync_semaphore.release()
                elif callback.callback != None:
                    self.engine.thread_pool.submit(callback.callback.callback, answer)
