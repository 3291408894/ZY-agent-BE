"""
班级管理系统 Pydantic Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 请求
# ============================================================
class ClassCreateReq(BaseModel):
    """教师创建班级"""
    name: str = Field(..., min_length=1, max_length=100, description="班级名称")
    grade: str = Field(..., min_length=1, max_length=50, description="年级")
    subject: str = Field(..., min_length=1, max_length=50, description="学科")
    description: str | None = Field(default=None, max_length=500, description="班级描述")


class JoinClassReq(BaseModel):
    """学生通过邀请码加入班级"""
    invite_code: str = Field(..., min_length=8, max_length=8, description="8位邀请码")


# ============================================================
# 响应
# ============================================================
class ClassItem(BaseModel):
    """班级列表项"""
    id: str
    name: str
    grade: str
    subject: str
    description: str | None = None
    invite_code: str
    student_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClassDetailResp(BaseModel):
    """班级详情"""
    id: str
    name: str
    grade: str
    subject: str
    description: str | None = None
    invite_code: str
    student_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentRosterItem(BaseModel):
    """花名册中学生项"""
    id: str  # ClassStudent 关联 ID
    student_id: str
    student_name: str
    joined_at: datetime


class InviteCodeResp(BaseModel):
    """邀请码响应"""
    invite_code: str


class JoinResultResp(BaseModel):
    """加入班级结果"""
    class_id: str
    class_name: str
    message: str
