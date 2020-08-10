#encoding=utf8

import threading
import socket
import hashlib
from enum import Enum
from .client_engine import ClientEngine
from .tcp_connection import *
from .quest import *
from .fpnn_error import *
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography import utils

__all__ = ('ConnectionCallback', 'QuestCallback', 'QuestProcessor', 'TCPClient', 'FPNN_SDK_VERSION')

FPNN_SDK_VERSION = '2.0.4'

class ConnectionStatus(Enum):
    NoConnected = 1
    Connecting = 2
    KeyExchanging = 3
    Connected = 4

class ConnectionCallback(object):
    def connected(self, connection_id, endpoint, connected):
        pass

    def closed(self, connection_id, endpoint, caused_by_error):
        pass

class QuestCallback(object):
    def callback(self, answer):
        pass

class QuestProcessor(object):
    def __init__(self):
        pass

class TCPClient(object):
    def __init__(self, host, port, auto_reconnect = True):
        self.lock = threading.Lock()
        self.auto_reconnect = auto_reconnect
        self.processor = None 
        self.connection_callback = None
        self.connected = False
        self.can_encryptor = True
        self.encryptor_curve = None
        self.encryptor_strength = None
        self.encrypted_key = None
        self.encrypted_iv = None
        self.encrypted_send_pub_key = None
        self.connect_status = ConnectionStatus.NoConnected
        self.quest_timeout = 0
        self.connect_timeout = 0
        self.engine = ClientEngine()
        self.connection_info = TCPConnectionInfo(host, port)
        self.current_connection = None
        self.error_recorder = None
        self.connection_id_cache = 0
        self.endpoint_cache = ''

    def set_auto_connect(self, auto_reconnect):
        self.auto_reconnect = auto_reconnect

    def set_connect_timeout(self, milliseconds):
        self.connect_timeout = milliseconds

    def set_quest_timeout(self, milliseconds):
        self.quest_timeout = milliseconds

    def set_error_recorder(self, recorder):
        self.error_recorder = recorder
        ClientEngine.error_recorder = recorder


    def set_quest_processor(self, processor):
        if not isinstance(processor, QuestProcessor):
            raise Exception("processor type error")
        self.processor = processor
        if self.current_connection != None:
            self.current_connection.processor = processor

    def set_connection_callback(self, callback):
        if  not isinstance(callback, ConnectionCallback):
            raise Exception("callback type error")
        self.connection_callback = callback
        if self.current_connection != None:
            self.current_connection.connection_callback = callback

    def enable_encryptor_by_pem_file(self, pem_pub_file, curve_name = 'secp256k1', strength = 128):
        if not self.can_encryptor:
            raise Exception("can not enable encryptor after a quest send")
        if curve_name not in ['secp256k1', 'secp256r1', 'secp192r1', 'secp224r1']:
            curve_name = 'secp256k1'
        self.encryptor_curve = ec.SECP256K1()
        if curve_name == 'secp256k1':
            self.encryptor_curve = ec.SECP256K1()
        elif curve_name == 'secp256r1':
            self.encryptor_curve = ec.SECP256R1()
        elif curve_name == 'secp192r1':
            self.encryptor_curve = ec.SECP192R1()
        else:
            self.encryptor_curve = ec.SECP224R1()
        if strength not in [128, 256]:
            strength = 128
        self.encryptor_strength = strength

        pri_key = ec.generate_private_key(self.encryptor_curve, default_backend())
        pub_key = pri_key.public_key()
        peer_pub_key = load_pem_public_key(open(pem_pub_file, 'rb').read(), backend=default_backend()) 
        
        secret = pri_key.exchange(ec.ECDH(), peer_pub_key)
        self.encrypted_iv = hashlib.md5(secret).digest()
        if strength == 128:
            self.encrypted_key = secret[0:16]
        else:
            if len(secret) == 32:
                self.encrypted_key = secret
            else:
                self.encrypted_key = hashlib.sha256(secret).digest()
        self.encrypted_send_pub_key = utils.int_to_bytes(pub_key.public_numbers().x, 32) + utils.int_to_bytes(pub_key.public_numbers().y, 32)

    def connect_callback(self, connection_id, endpoint, connected):
        if self.connection_callback != None:
            self.connection_callback.connected(connection_id, endpoint, connected)

    def close_callback(self, connection_id, endpoint, caused_by_error):
        if self.connection_callback != None:
            self.connection_callback.closed(connection_id, endpoint, caused_by_error)

    def connect(self):
        with self.lock:
            if self.connected:
                return True

            self.connect_status = ConnectionStatus.Connecting

            socket_fd = 0
            try:
                server_address = (self.connection_info.host, self.connection_info.port)
                socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if self.connect_timeout > 0:
                    socket_fd.settimeout(self.connect_timeout / 1000)
                socket_fd.connect(server_address)
                socket_fd.setblocking(False)
            except:
                self.connect_status = ConnectionStatus.NoConnected
                self.engine.thread_pool_execute(self.connect_callback, (0, self.connection_info.host + ':' + str(self.connection_info.port), False))
                return False
        
            if socket_fd == 0:
                self.connect_status = ConnectionStatus.NoConnected
                self.engine.thread_pool_execute(self.connect_callback, (0, self.connection_info.host + ':' + str(self.connection_info.port), False))
                return False

            self.current_connection = TCPConnection(self, self.engine, self.connection_info, socket_fd)

            if self.processor != None:
                self.current_connection.processor = self.processor

            if self.connection_callback != None:
                self.current_connection.connection_callback = self.connection_callback

            self.connected = True
            self.connect_status = ConnectionStatus.Connected

            self.engine.thread_pool_execute(self.connect_callback, (self.current_connection.connection_id, self.connection_info.host + ':' + str(self.connection_info.port), True))

            self.engine.join(self.current_connection)

            if self.encryptor_curve != None:
                self.current_connection.connection_info.encrypted = True
                self.current_connection.connection_info.encrypted_key = self.encrypted_key
                self.current_connection.connection_info.encrypted_iv = self.encrypted_iv
                self.current_connection.need_read_lenth = 4
                self.current_connection.read_step = ReadPackageStep.READ_HEADER_ENCRYPTOR

                encryptor_quest = Quest('*key')
                encryptor_quest.param('publicKey', self.encrypted_send_pub_key)
                encryptor_quest.param('streamMode', False)
                encryptor_quest.param('bits', self.encryptor_strength)
                answer = self.send_quest(encryptor_quest)

                if answer.is_error():
                    self.engine.quit(self.current_connection)
                    self.current_connection.clean_callback()
                    self.engine.thread_pool_execute(self.close_callback, (self.current_connection.connection_id, self.connection_info.host + ':' + str(self.connection_info.port), True))
                    self.current_connection = None
                    self.connected = False
                    self.connect_status = ConnectionStatus.NoConnected

            self.can_encryptor = False
            return True

    def close(self):
        with self.lock:
            if not self.connected:
                return
            if self.current_connection != None:
                self.engine.quit(self.current_connection)
                self.current_connection.clean_callback()
                self.engine.thread_pool_execute(self.close_callback, (self.current_connection.connection_id, self.connection_info.host + ':' + str(self.connection_info.port), False))
                self.current_connection = None
            self.connected = False
            self.connect_status = ConnectionStatus.NoConnected

    def reconnect(self):
        self.close()
        return self.connect()

    def notice_closed(self):
        with self.lock:
            self.current_connection = None
            self.connected = False
            self.connect_status = ConnectionStatus.NoConnected

    def send_quest(self, quest, callback = None, timeout = 0):
        if not isinstance(quest, Quest):
            raise Exception("quest type error")

        if callback != None and not isinstance(callback, QuestCallback):
            raise Exception("callback type error")

        quest.create_sequnce_num()
        is_async = quest.oneway or callback != None

        if not self.connected:
            if self.auto_reconnect:
                if not self.connect():
                    answer = Answer()
                    answer.sequnce_num = quest.sequnce_num
                    answer.set_error(FPNN_ERROR.FPNN_EC_CORE_INVALID_CONNECTION.value, 'invalid connection')
                    if is_async:
                        callback.callback(answer)
                        return None
                    else:
                        return answer
            else:
                answer = Answer()
                answer.sequnce_num = quest.sequnce_num
                answer.set_error(FPNN_ERROR.FPNN_EC_CORE_INVALID_CONNECTION.value, 'invalid connection')
                if is_async:
                    callback.callback(answer)
                    return None
                else:
                    return answer

        if timeout == 0:
            timeout = self.quest_timeout

        fpnn_callback = FpnnQuestCallback(callback, timeout)
        if is_async:
            self.send(quest, fpnn_callback, timeout)
        else:
            fpnn_callback.sync_semaphore = threading.Semaphore(0)
            self.send(quest, fpnn_callback, timeout)
            fpnn_callback.sync_semaphore.acquire()
            return fpnn_callback.sync_answer

    def send(self, quest, callback, timeout):
        if self.current_connection != None:
            self.current_connection.send_quest(quest, callback, timeout)

    def destory(self):
        self.close()
        self.engine.stop()

