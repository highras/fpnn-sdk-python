#encoding=utf8

import time
import struct
import msgpack
from enum import Enum

__all__ = ('Quest', 'Answer', 'FpnnMType')

FPNN_FLAG_MSGPACK = 0x80

class FpnnMType(Enum):
    FPNN_MT_ONEWAY = 0
    FPNN_MT_TWOWAY = 1
    FPNN_MT_ANSWER = 2

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
                           self.magic.encode('utf-8'),
                           self.version,
                           self.flag,
                           self.mtype,
                           self.ss,
                           self.psize)

class Message(object):
    def __init__(self, params = None):
        self.header = Header("FPNN", 0, 0, 0, 0, 0)
        self.params_map = {}
        if isinstance(params, dict):
            for (key, value) in params.items():
                if not isinstance(key, str):
                    raise Exception('params key must be a str')
                self.params_map[key] = value

    def param(self, key, value):
        if not isinstance(key, str):
            raise Exception('key must a str in Quest param')
        self.params_map[key] = value

    def get(self, key, default):
        if not isinstance(key, str):
            raise Exception('key must a str in Quest param')
        value = self.params_map.get(key, None)
        if value == None:
            return default
        else:
            return value

    def want(self, key):
        value = self.get(key, None)
        if value == None:
            raise Exception('get param error')
        return value

class Quest(Message):
    next_sequnce = 0
    def __init__(self, method, oneway = False, params = None):
        Message.__init__(self, params)
        self.method = method
        self.oneway = oneway
        self.sequnce_num = None

    def __str__(self):
        return 'Quest: seq({0}) method({1}) oneway({2}) params({3})'.format(self.sequnce_num, self.method, self.oneway, str(self.params_map))

    def raw(self):
        self.header.flag = FPNN_FLAG_MSGPACK
        self.header.mtype = FpnnMType.FPNN_MT_ONEWAY.value if self.oneway else FpnnMType.FPNN_MT_TWOWAY.value
        self.header.ss = len(self.method)
        if not self.oneway and self.sequnce_num == None:
            self.sequnce_num = self.next_sequnce_num()
        self.payload = msgpack.packb(self.params_map)
        self.header.psize = len(self.payload)
        packet = self.header.pack()
        if self.header.mtype == FpnnMType.FPNN_MT_TWOWAY.value:
            packet += struct.pack('<I', self.sequnce_num)
        packet += struct.pack('!%ds%ds' % (len(self.method), len(self.payload)),
                              self.method.encode('utf-8'),
                              self.payload)
        return packet

    def create_sequnce_num(self):
        if not self.oneway:
            self.sequnce_num = self.next_sequnce_num()

    @classmethod
    def next_sequnce_num(cls):
        if cls.next_sequnce >= 2147483647:
            cls.next_sequnce = 0
        cls.next_sequnce += 1
        return cls.next_sequnce

class Answer(Message):
    def __init__(self, params = None):
        Message.__init__(self, params)
        self.sequnce_num = None
        self.error_code = None
        self.error_message = None            

    def __str__(self):
        if self.is_error():
            return 'Exception: seq({0}) code({1}) message({2})'.format(self.sequnce_num, self.error_code, self.error_message)
        else:
            return 'Answer: seq({0}) params({1})'.format(self.sequnce_num, str(self.params_map))

    def set_error(self, code, message):
        self.error_code = code
        self.error_message = message

    def is_error(self):
        return self.error_code != None or self.error_message != None

    def set_params(self, params):
        self.params_map = params

    def raw(self):
        if self.sequnce_num == None:
            raise Exception("a seq num can not be None in Answer")

        self.header.flag = FPNN_FLAG_MSGPACK
        self.header.mtype = FpnnMType.FPNN_MT_ANSWER.value
        if self.is_error():
            self.payload = msgpack.packb({'code': self.error_code, 'ex': self.error_code})
            self.header.ss = 1
        else:
            self.payload = msgpack.packb(self.params_map)
            self.header.ss = 0
        self.header.psize = len(self.payload)
        packet = self.header.pack()
        packet += struct.pack('<I', self.sequnce_num)
        packet += struct.pack('!%ds' % (len(self.payload)),
                              self.payload)
        return packet

    