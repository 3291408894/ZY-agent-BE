"""
通用 Schema — 统一响应格式、错误码、分页
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

# ============================================================
# 错误码常量
# ============================================================


class ErrorCode:
    """错误码定义（与接口文档附录 A.3 一致）"""

    SUCCESS = 0
    # 400xx — 参数/校验
    PARAM_INVALID = 40001
    FILE_FORMAT_UNSUPPORTED = 40002
    FILE_SIZE_EXCEEDED = 40003
    # 401xx — 认证
    TOKEN_EXPIRED = 40101
    TOKEN_INVALID = 40102
    # 403xx — 权限
    FORBIDDEN = 40301
    # 404xx — 资源不存在
    USER_NOT_FOUND = 40401
    RESOURCE_NOT_FOUND = 40402
    # 409xx — 冲突
    USER_EXISTS = 40901
    # 429xx — 限流
    RATE_LIMITED = 42901
    # 500xx — 服务器
    INTERNAL_ERROR = 50001
    LLM_SERVICE_ERROR = 50002
    FILE_PARSE_ERROR = 50003


# ============================================================
# 统一响应
# ============================================================


class APIResponse(BaseModel, Generic[T]):
    """统一成功响应"""

    code: int = ErrorCode.SUCCESS
    message: str = "ok"
    data: T | None = None


class APIError(BaseModel):
    """统一错误响应"""

    code: int
    message: str
    detail: Any | None = None


# ============================================================
# 分页
# ============================================================


class PaginationParams(BaseModel):
    """分页请求参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class PaginatedData(BaseModel, Generic[T]):
    """分页响应"""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def make_response(data: Any = None, message: str = "ok") -> dict:
    """快速构造统一响应（函数式风格）"""
    return {"code": ErrorCode.SUCCESS, "message": message, "data": data}


def make_paginated_response(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """快速构造分页响应"""
    return {
        "code": ErrorCode.SUCCESS,
        "message": "ok",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
        },
    }
