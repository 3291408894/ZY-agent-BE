"""智能教案生成 — SQLAlchemy 数据模型 (PBI_LP)"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LessonPlan(Base):
    """教案记录表"""

    __tablename__ = "lesson_plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键 UUID"
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="所属用户",
    )
    title: Mapped[str] = mapped_column(
        String(128), default="未命名教案", comment="教案标题（AI 自动提取）"
    )
    subject: Mapped[str] = mapped_column(
        String(32), comment="学科"
    )
    grade: Mapped[str] = mapped_column(
        String(16), comment="年级"
    )
    textbook_version: Mapped[str] = mapped_column(
        String(64), default="", comment="教材版本"
    )
    unit_chapter: Mapped[str] = mapped_column(
        String(128), default="", comment="单元/章节"
    )
    class_hours: Mapped[int] = mapped_column(
        Integer, default=1, comment="课时数"
    )
    teaching_objectives: Mapped[str] = mapped_column(
        Text, comment="用户输入的教学目标"
    )
    requirements: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="特殊要求"
    )
    plan_content: Mapped[str] = mapped_column(
        Text, comment="AI 生成的教案正文（Markdown）"
    )
    sections: Mapped[list] = mapped_column(
        JSON, default=list, comment="结构化分段信息"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="创建时间"
    )

    # 关联
    user: Mapped["User"] = relationship(back_populates="lesson_plans")
