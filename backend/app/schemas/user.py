"""
用户相关 Pydantic Schema (PBI_01)
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- 注册 ---
class RegisterReq(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=64)
    grade: str = Field(..., description="年级，如'七年级'")
    subjects: list[str] = Field(default_factory=list)


class RegisterResp(BaseModel):
    user_id: str
    email: str | None
    grade: str


# --- 登录 ---
class LoginReq(BaseModel):
    login: str = Field(..., description="邮箱或手机号")
    password: str


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
    token_type: str = "bearer"
    expires_in: int
    user: UserBrief


# --- 用户资料 ---
class UpdateProfileReq(BaseModel):
    nickname: str | None = None
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
    created_at: datetime


# --- 仪表盘 (PBI_02) ---
class DashboardResp(BaseModel):
    total_study_time: int = 0
    total_exercises: int = 0
    correct_rate: float = 0.0
    recent_summaries: list[dict] = []
    recent_exercises: list[dict] = []
    recommendations: list[dict] = []
    weak_points: list[str] = []
