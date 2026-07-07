"""
API 依赖注入 — 数据库会话、当前用户、权限校验
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.schemas.common import ErrorCode

security = HTTPBearer(auto_error=False)


async def get_db():
    """每个请求获取独立的数据库会话，请求结束后自动提交/回滚"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 解析当前用户，未登录则抛 401"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_INVALID,
                "message": "缺少认证令牌，请在 Header 中提供 Authorization: Bearer <token>",
                "detail": None,
            },
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_EXPIRED,
                "message": "Token 无效或已过期，请重新登录",
                "detail": None,
            },
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_INVALID,
                "message": "请使用 Access Token（而非 Refresh Token）访问此接口",
                "detail": None,
            },
        )

    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.USER_NOT_FOUND,
                "message": "用户不存在或账户已被禁用",
                "detail": None,
            },
        )
    return user


async def get_current_teacher(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户为教师角色，否则返回 403"""
    if current_user.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN,
                "message": "仅教师可访问此功能",
                "detail": None,
            },
        )
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选认证 — 有 Token 就解析，没有则返回 None"""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        return await db.get(User, payload["sub"])
    except Exception:
        return None
