"""认证模块 — API 路由 (PBI_01)"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

router = APIRouter()


# ── 请求/响应模型 ──

class RegisterReq(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=64)
    grade: str = ""
    subjects: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("邮箱和手机号至少填写一项")
        return self


class LoginReq(BaseModel):
    login: str = Field(..., min_length=1, description="邮箱或手机号")
    password: str = Field(..., min_length=1)


# ── 路由 ──

@router.post("/register", status_code=201)
async def register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    # 查重
    if req.email:
        result = await db.execute(select(User.id).where(User.email == req.email).limit(1))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该邮箱已被注册")
    if req.phone:
        result = await db.execute(select(User.id).where(User.phone == req.phone).limit(1))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该手机号已被注册")

    user = User(
        email=req.email,
        phone=req.phone,
        hashed_password=hash_password(req.password),
        grade=req.grade,
        subjects=req.subjects,
    )
    db.add(user)
    await db.flush()

    # 生成 JWT
    access_token = create_access_token(user.id)
    return {
        "code": 0,
        "message": "注册成功",
        "data": {
            "user_id": user.id,
            "email": user.email,
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 86400,
        },
    }


@router.post("/login")
async def login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    """登录获取 JWT Token"""
    result = await db.execute(
        select(User).where((User.email == req.login) | (User.phone == req.login))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    access_token = create_access_token(user.id)
    return {
        "code": 0,
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 86400,
            "user": {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "nickname": user.nickname,
                "grade": user.grade,
                "subjects": user.subjects or [],
            },
        },
    }
