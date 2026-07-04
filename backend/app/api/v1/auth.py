"""
认证路由 (PBI_01) — 注册、登录、密码重置
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_response
from app.schemas.user import LoginReq, LoginResp, RegisterReq, RegisterResp, UserBrief
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", summary="用户注册")
async def register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    """注册新用户，自动创建学习档案"""
    service = UserService(db)
    # 校验邮箱/手机号唯一性
    existing = await service.get_by_email_or_phone(req.email, req.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": ErrorCode.USER_EXISTS, "message": "邮箱或手机号已被注册"},
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
            detail={"code": ErrorCode.TOKEN_INVALID, "message": "账号或密码错误"},
        )
    await db.commit()
    return make_response(data=result, message="登录成功")


@router.post("/reset-password", summary="重置密码")
async def reset_password(
    email: str = None,
    phone: str = None,
    new_password: str = None,
    db: AsyncSession = Depends(get_db),
):
    """通过邮箱或手机号重置密码（简化版，生产环境需发送验证码）"""
    # TODO: 生产环境需要先发送验证码验证身份
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": "请提供邮箱或手机号"},
        )
    service = UserService(db)
    user = await service.get_by_email_or_phone(email, phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.USER_NOT_FOUND, "message": "用户不存在"},
        )
    await service.reset_password(user, new_password)
    await db.commit()
    return make_response(message="密码重置成功")
