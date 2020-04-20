#encoding=utf8

from enum import Enum

__all__ = ('FPNN_ERROR', 'FpnnException')

class FPNN_ERROR(Enum):
    FPNN_EC_UNKNOWN_ERROR = 10001
    FPNN_EC_CONNECTION_NOT_CONNECTED = 10002
    FPNN_EC_CONNECTION_IS_CLOSE = 10003
    FPNN_EC_QUEST_TIMEOUT = 10004
    FPNN_EC_CONNECT_ERROR = 10005
	
class FpnnException(Exception):
    def __init__(self, code, message):
        if isinstance(code, FPNN_ERROR):
            self.code = code.value
        else:
            self.code = code
        self.message = message

    def __str__(self):
        return 'FPNN Exception {0} : {1}'.format(self.code, self.message)