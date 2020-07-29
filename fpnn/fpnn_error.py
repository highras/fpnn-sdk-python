#encoding=utf8

from enum import Enum

__all__ = ('FPNN_ERROR', 'FpnnException')

class FPNN_ERROR(Enum):
    FPNN_EC_OK							= 0
    # for proto
    FPNN_EC_PROTO_UNKNOWN_ERROR			= 10001
    FPNN_EC_PROTO_NOT_SUPPORTED			= 10002
    FPNN_EC_PROTO_INVALID_PACKAGE		= 10003
    FPNN_EC_PROTO_JSON_CONVERT			= 10004
    FPNN_EC_PROTO_STRING_KEY			= 10005
    FPNN_EC_PROTO_MAP_VALUE				= 10006
    FPNN_EC_PROTO_METHOD_TYPE			= 10007
    FPNN_EC_PROTO_PROTO_TYPE			= 10008
    FPNN_EC_PROTO_KEY_NOT_FOUND			= 10009
    FPNN_EC_PROTO_TYPE_CONVERT			= 10010
    FPNN_EC_PROTO_FILE_SIGN				= 10011
    FPNN_EC_PROTO_FILE_NOT_EXIST		= 10012
    # for core
    FPNN_EC_CORE_UNKNOWN_ERROR			= 20001
    FPNN_EC_CORE_CONNECTION_CLOSED		= 20002
    FPNN_EC_CORE_TIMEOUT				= 20003
    FPNN_EC_CORE_UNKNOWN_METHOD			= 20004
    FPNN_EC_CORE_ENCODING				= 20005
    FPNN_EC_CORE_DECODING				= 20006
    FPNN_EC_CORE_SEND_ERROR				= 20007
    FPNN_EC_CORE_RECV_ERROR				= 20008
    FPNN_EC_CORE_INVALID_PACKAGE		= 20009
    FPNN_EC_CORE_HTTP_ERROR				= 20010
    FPNN_EC_CORE_WORK_QUEUE_FULL		= 20011
    FPNN_EC_CORE_INVALID_CONNECTION		= 20012
    FPNN_EC_CORE_FORBIDDEN				= 20013
    FPNN_EC_CORE_SERVER_STOPPING		= 20014
    # for other
    FPNN_EC_ZIP_COMPRESS				= 30001
    FPNN_EC_ZIP_DECOMPRESS				= 30002

class FpnnException(Exception):
    def __init__(self, code, message):
        if isinstance(code, FPNN_ERROR):
            self.code = code.value
        else:
            self.code = code
        self.message = message

    def __str__(self):
        return 'FPNN Exception {0} : {1}'.format(self.code, self.message)