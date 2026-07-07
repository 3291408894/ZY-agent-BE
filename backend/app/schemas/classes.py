"""
班级管理系统 Schema — 创建/加入/花名册/邀请码 (功能4)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 枚举
# ============================================================

class ClassStatusEnum(str):
    ACTIVE = "active"
    ARCHIVED = "archived"


# ============================================================
# 创建班级
# ============================================================

class ClassCreate(BaseModel):
    """创建班级请求"""
    name: str = Field(..., min_length=1, max_length=100, description="班级名称")
    grade: str = Field(..., min_length=1, max_length=50, description="年级")
    subject: str = Field(..., min_length=1, max_length=50, description="学科")
    description: str | None = Field(default=None, max_length=500, description="班级描述")


class ClassUpdate(BaseModel):
    """更新班级信息"""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


# ============================================================
# 班级响应
# ============================================================

class ClassStudentBrief(BaseModel):
    """花名册学生简要信息"""
    id: str
    student_id: str
    nickname: str
    avatar_url: str | None
    joined_at: datetime

    class Config:
        from_attributes = True


class ClassResponse(BaseModel):
    """班级信息响应"""
    id: str
    teacher_id: str
    name: str
    grade: str
    subject: str
    description: str | None
    invite_code: str
    student_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClassDetailResponse(ClassResponse):
    """班级详情（含花名册）"""
    students: list[ClassStudentBrief] = []


class ClassRosterResponse(BaseModel):
    """花名册响应"""
    class_id: str
    class_name: str
    student_count: int
    students: list[ClassStudentBrief]


# ============================================================
# 学生端 — 加入班级
# ============================================================

class JoinClassRequest(BaseModel):
    """通过邀请码加入班级"""
    invite_code: str = Field(..., min_length=6, max_length=10, description="邀请码")


class JoinClassConfirm(BaseModel):
    """加入班级前确认信息"""
    class_id: str
    class_name: str
    teacher_name: str
    subject: str
    grade: str


class StudentClassItem(BaseModel):
    """学生端班级列表项"""
    id: str
    name: str
    grade: str
    subject: str
    teacher_name: str
    student_count: int
    joined_at: datetime

    class Config:
        from_attributes = True
