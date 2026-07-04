"""
用户相关 Pydantic Schema (PBI_01)
"""

from datetime import datetime

<<<<<<< HEAD
from pydantic import BaseModel, Field, model_validator
=======
from pydantic import BaseModel, EmailStr, Field, model_validator
>>>>>>> main


# ============================================================
# 注册
# ============================================================
class RegisterReq(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=64, description="密码，8-64 位")
    grade: str = Field(..., description="年级，如'七年级'")
<<<<<<< HEAD
    subjects: list[str] = Field(default_factory=list, description="学科偏好，至少1个")
=======
    subjects: list[str] = Field(default_factory=list, description="学科偏好列表")
>>>>>>> main

    @model_validator(mode="after")
    def check_email_or_phone(self):
        if not self.email and not self.phone:
<<<<<<< HEAD
            raise ValueError("邮箱和手机号至少需要提供一个")
=======
            raise ValueError("邮箱和手机号至少填写一项")
>>>>>>> main
        return self


class RegisterResp(BaseModel):
    user_id: str
    email: str | None
    phone: str | None
    grade: str


# ============================================================
# 登录
# ============================================================
class LoginReq(BaseModel):
    login: str = Field(..., min_length=1, description="邮箱或手机号")
    password: str = Field(..., min_length=1)


class UserBrief(BaseModel):
    id: str
    email: str | None
    phone: str | None
    nickname: str
    grade: str | None
    subjects: list[str]
    textbook_version: str | None
    avatar_url: str | None


class LoginResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserBrief


# ============================================================
# Token 刷新
# ============================================================
class RefreshTokenReq(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")


class RefreshTokenResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================
# 密码重置
# ============================================================
class ResetPasswordReq(BaseModel):
    """发送密码重置验证码"""
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def check_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("邮箱和手机号至少填写一项")
        return self


class ResetPasswordVerifyReq(BaseModel):
    """验证码校验 + 设置新密码"""
    email: EmailStr | None = None
    phone: str | None = None
    code: str = Field(..., min_length=6, max_length=6, description="6 位验证码")
    new_password: str = Field(..., min_length=8, max_length=64)

    @model_validator(mode="after")
    def check_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("邮箱和手机号至少填写一项")
        return self


# ============================================================
# 用户资料
# ============================================================
class UpdateProfileReq(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    grade: str | None = None
    subjects: list[str] | None = None
    textbook_version: str | None = None


class UserProfileResp(BaseModel):
    id: str
    email: str | None
    phone: str | None
    nickname: str
    grade: str | None
    subjects: list[str]
    textbook_version: str | None
    avatar_url: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- 密码重置 ---
class SendResetCodeReq(BaseModel):
    email: str = Field(..., description="接收验证码的邮箱")


class VerifyResetCodeReq(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6, description="6位验证码")
    new_password: str = Field(..., min_length=8, max_length=64, description="新密码")


# ============================================================
# 修改密码（已登录）
# ============================================================
class ChangePasswordReq(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=64, description="新密码，8-64 位")


# ============================================================
# 仪表盘 (PBI_02)
# ============================================================
class DashboardResp(BaseModel):
    total_study_time: int = 0
    total_exercises: int = 0
    correct_rate: float = 0.0
    recent_summaries: list[dict] = []
    recent_exercises: list[dict] = []
    recommendations: list[dict] = []
    weak_points: list[str] = []
