"""
班级管理系统模型 (功能4) — Class + ClassStudent
"""

import uuid
import secrets
import string
from datetime import datetime

from sqlalchemy import (
    CHAR, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def generate_invite_code(length: int = 8) -> str:
    """生成易读的邀请码，排除易混淆字符 0/O/1/I/L"""
    alphabet = string.ascii_uppercase + string.digits
    exclude = {'0', 'O', '1', 'I', 'L'}
    chars = [c for c in alphabet if c not in exclude]
    return ''.join(secrets.choice(chars) for _ in range(length))


class Class(Base):
    """班级主表"""

    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), comment="班级名称")
    grade: Mapped[str] = mapped_column(String(50), comment="年级")
    subject: Mapped[str] = mapped_column(String(50), comment="学科")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="班级描述")
    invite_code: Mapped[str] = mapped_column(
        CHAR(8), unique=True, comment="邀请码（6-8位字母数字）"
    )
    student_count: Mapped[int] = mapped_column(Integer, default=0, comment="学生人数（冗余）")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active/archived"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    teacher: Mapped["User"] = relationship(back_populates="classes")
    students_rel: Mapped[list["ClassStudent"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    shared_resources: Mapped[list["ClassResource"]] = relationship(back_populates="class_", cascade="all, delete-orphan")


class ClassStudent(Base):
    """班级学生关联表"""

    __tablename__ = "class_students"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_cs_class_stu"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    class_: Mapped["Class"] = relationship(back_populates="students_rel")
    student: Mapped["User"] = relationship(back_populates="class_memberships")
