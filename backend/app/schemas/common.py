"""统一响应格式 + 错误码 + 分页工具"""

from enum import IntEnum


class ErrorCode(IntEnum):
    """API 错误码（与接口文档附录 A.3 对齐）"""
    SUCCESS = 0
    VALIDATION_ERROR = 40001
    FILE_TYPE_UNSUPPORTED = 40002
    FILE_SIZE_EXCEEDED = 40003
    TOKEN_EXPIRED = 40101
    TOKEN_INVALID = 40102
    FORBIDDEN = 40301
    USER_NOT_FOUND = 40401
    RESOURCE_NOT_FOUND = 40402
    DUPLICATE_ENTRY = 40901
    RATE_LIMITED = 42901
    INTERNAL_ERROR = 50001
    LLM_SERVICE_ERROR = 50002
    FILE_PARSE_ERROR = 50003


def success_response(data=None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def error_response(code: ErrorCode, message: str, detail: str | None = None) -> dict:
    return {"code": code.value, "message": message, "detail": detail}
