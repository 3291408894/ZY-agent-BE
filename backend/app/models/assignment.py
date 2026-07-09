"""
作业管理系统模型 (功能5) — Assignment + AssignmentSubmission
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Assignment(Base):
    """作业主表"""

    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exam_paper_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exam_papers.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="关联的试卷ID（从试卷发布创建时填充）"
    )
    title: Mapped[str] = mapped_column(String(200), comment="作业标题")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="作业说明/要求")
    subject: Mapped[str] = mapped_column(String(50), comment="学科")
    content: Mapped[dict] = mapped_column(JSON, comment="作业内容JSON")
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总分")
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="截止时间")
    allow_late_submission: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许迟交")
    submission_count: Mapped[int] = mapped_column(Integer, default=0, comment="已提交人数")
    graded_count: Mapped[int] = mapped_column(Integer, default=0, comment="已批改人数")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active/closed/archived"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    class_: Mapped["Class"] = relationship(back_populates="assignments")
    teacher: Mapped["User"] = relationship(back_populates="assignments")
    submissions: Mapped[list["AssignmentSubmission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class AssignmentSubmission(Base):
    """作业提交表"""

    __tablename__ = "assignment_submissions"
    __table_args__ = (
        # unique constraint is defined via SQL-level via migration, but we ensure at app level
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[dict] = mapped_column(JSON, comment="作答内容JSON")
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="附件列表")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="得分")
    ai_feedback: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="AI批改反馈"
    )
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True, comment="教师评语")
    teacher_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="批改教师ID"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", comment="submitted/grading/graded/returned"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="提交时间"
    )
    graded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="批改时间"
    )

    # 关系
    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student: Mapped["User"] = relationship(
        back_populates="submissions", foreign_keys=[student_id]
    )
    grading_teacher: Mapped["User | None"] = relationship(
        back_populates="graded_submissions", foreign_keys=[teacher_id]
    )
