"""
认证路由 (PBI_01) — 注册、登录、密码重置、Token 刷新
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ErrorCode, make_response
from app.schemas.user import (
    LoginReq,
    RefreshTokenReq,
    RegisterReq,
    ResetPasswordReq,
    ResetPasswordVerifyReq,
)
from app.services.user_service import UserService

router = APIRouter()


# ================================================================
# POST /auth/register — 用户注册
# ================================================================
@router.post("/register", status_code=201)
async def register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    """
    注册新用户，成功后自动创建学习档案。

    - **email** / **phone**：至少填写一项
    - **password**：8-64 位
    - **grade**：年级，如"七年级"
    - **subjects**：学科偏好列表
    """
    service = UserService(db)
    user = await service.register(req)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.USER_EXISTS,
                "message": "该邮箱或手机号已被注册",
                "detail": None,
            },
        )
    await db.commit()
    await db.refresh(user)  # commit 后刷新，避免 MissingGreenlet
    return make_response(
        data={
            "user_id": user.id,
            "email": user.email,
            "phone": user.phone,
            "grade": user.grade,
        },
        message="注册成功",
    )


# ================================================================
# POST /auth/login — 用户登录
# ================================================================
@router.post("/login")
async def login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    """
    使用邮箱或手机号登录，返回 JWT Token 和用户基本信息。

    - **login**：邮箱或手机号
    - **password**：密码
    """
    service = UserService(db)
    result = await service.login(req)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_INVALID,
                "message": "账号或密码错误，或账户已被禁用",
                "detail": None,
            },
        )

    return make_response(data=result)


# ================================================================
# POST /auth/refresh — 刷新 Token
# ================================================================
@router.post("/refresh")
async def refresh_token(req: RefreshTokenReq, db: AsyncSession = Depends(get_db)):
    """使用 refresh_token 获取新的 access_token"""
    service = UserService(db)
    result = await service.refresh_access_token(req.refresh_token)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_INVALID,
                "message": "Refresh Token 无效或已过期",
                "detail": None,
            },
        )

    return make_response(data=result)


# ================================================================
# POST /auth/reset-password — 发送密码重置验证码
# ================================================================
@router.post("/reset-password")
async def reset_password(req: ResetPasswordReq, db: AsyncSession = Depends(get_db)):
    """
    向已注册的邮箱或手机号发送 6 位验证码。

    验证码有效期 5 分钟，开发阶段会打印到服务端日志。
    """
    service = UserService(db)
    target = await service.send_reset_code(req)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.USER_NOT_FOUND,
                "message": "该邮箱或手机号未注册",
                "detail": None,
            },
        )

    # 不暴露完整邮箱/手机号
    masked = target[:3] + "****" + target[-3:] if len(target) > 6 else target[:1] + "****"
    return make_response(
        data={"target": masked},
        message="验证码已发送，有效期 5 分钟",
    )


# ================================================================
# POST /auth/reset-password/verify — 验证码校验 + 重置密码
# ================================================================
@router.post("/reset-password/verify")
async def reset_password_verify(req: ResetPasswordVerifyReq, db: AsyncSession = Depends(get_db)):
    """
    校验验证码并设置新密码。

    - **code**：6 位验证码
    - **new_password**：新密码，8-64 位
    """
    service = UserService(db)
    user = await service.verify_reset_code(req)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.PARAM_INVALID,
                "message": "验证码错误或已过期",
                "detail": None,
            },
        )

    return make_response(message="密码已成功重置，请使用新密码登录")
