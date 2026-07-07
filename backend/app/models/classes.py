"""
班级管理系统模型 — Class + ClassStudent
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    teacher_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    grade: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invite_code: Mapped[str] = mapped_column(
        String(8), unique=True, comment="8位邀请码"
    )
    student_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active / archived"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关系
    teacher: Mapped["User"] = relationship(
        back_populates="owned_classes", foreign_keys=[teacher_id]
    )
    students: Mapped[list["ClassStudent"]] = relationship(
        back_populates="class_", cascade="all, delete-orphan"
    )


class ClassStudent(Base):
    __tablename__ = "class_students"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    class_: Mapped["Class"] = relationship(back_populates="students")
    student: Mapped["User"] = relationship(
        back_populates="class_memberships", foreign_keys=[student_id]
    )
