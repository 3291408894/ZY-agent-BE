"""
认证路由 (PBI_01) — 注册、登录、密码重置
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.common import ErrorCode, make_response
from app.schemas.user import (
    LoginReq,
    RegisterReq,
    RegisterResp,
    SendResetCodeReq,
    VerifyResetCodeReq,
)
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", summary="用户注册", status_code=201)
async def register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    """注册新用户，自动创建学习档案"""
    service = UserService(db)
    # 校验邮箱/手机号唯一性
    existing = await service.get_by_email_or_phone(req.email, req.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": ErrorCode.USER_EXISTS, "message": "邮箱或手机号已被注册", "detail": None},
        )
    user = await service.register(req)
    await db.commit()
    return make_response(
        data=RegisterResp(
            user_id=user.id,
            email=user.email,
            grade=user.grade,
        ).model_dump(),
        message="注册成功",
    )


@router.post("/login", summary="用户登录")
async def login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    """邮箱/手机号 + 密码登录，返回 JWT Token"""
    service = UserService(db)
    result = await service.login(req)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.TOKEN_INVALID, "message": "账号或密码错误", "detail": None},
        )
    await db.commit()
    return make_response(data=result)


@router.post("/reset-password", summary="发送重置密码验证码")
async def send_reset_code(req: SendResetCodeReq, db: AsyncSession = Depends(get_db)):
    """向邮箱发送 6 位验证码，有效期 300s（存入 Redis）"""
    service = UserService(db)
    user = await service.get_by_email(req.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.USER_NOT_FOUND, "message": "该邮箱未注册", "detail": None},
        )

    # 生成 6 位验证码
    code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

    # 存入 Redis，TTL 300s
    redis = await get_redis()
    await redis.setex(f"reset_code:{req.email}", 300, code)

    # TODO: 生产环境需通过邮件服务发送验证码
    # 开发环境下将验证码打印到日志
    import logging
    logging.getLogger("uvicorn").info(f"[DEV] 密码重置验证码 for {req.email}: {code}")

    return make_response(message="验证码已发送")


@router.post("/reset-password/verify", summary="验证并重置密码")
async def verify_and_reset(req: VerifyResetCodeReq, db: AsyncSession = Depends(get_db)):
    """验证 6 位验证码并重置密码"""
    service = UserService(db)

    # 从 Redis 获取验证码
    redis = await get_redis()
    stored_code = await redis.get(f"reset_code:{req.email}")
    if not stored_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": "验证码已过期，请重新获取", "detail": None},
        )
    if stored_code != req.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": "验证码错误", "detail": None},
        )

    # 查找用户
    user = await service.get_by_email(req.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.USER_NOT_FOUND, "message": "用户不存在", "detail": None},
        )

    # 重置密码
    await service.reset_password(user, req.new_password)
    await db.commit()

    # 删除已用验证码
    await redis.delete(f"reset_code:{req.email}")

    return make_response(message="密码重置成功")
