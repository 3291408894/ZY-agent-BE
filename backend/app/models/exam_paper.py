"""AI试卷生成记录 — SQLAlchemy 数据模型 (功能2: 试卷生成器)"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExamPaper(Base):
    """AI试卷生成记录表"""

    __tablename__ = "exam_papers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="试卷ID"
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="创建教师ID",
    )
    title: Mapped[str] = mapped_column(String(200), comment="试卷标题")
    subject: Mapped[str] = mapped_column(String(50), comment="学科")
    grade: Mapped[str] = mapped_column(String(50), comment="年级")
    exam_type: Mapped[str] = mapped_column(
        String(30), comment="考试类型: unit_test/midterm/final"
    )
    total_score: Mapped[int] = mapped_column(Integer, comment="总分")
    difficulty_ratio: Mapped[dict] = mapped_column(
        JSON, comment='难度配比: {"easy":30,"medium":50,"hard":20}'
    )
    question_structure: Mapped[list] = mapped_column(
        JSON, comment='题型分布: [{"type":"选择","count":10,"score_per":3,"subtotal":30}]'
    )
    content: Mapped[dict] = mapped_column(
        JSON, comment="试卷正文JSON: {header, sections[], answer_key, scoring_guide}"
    )
    answer_sheet: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="答题卡JSON（服务端自动生成）"
    )
    export_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="导出URL"
    )
    export_format: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="导出格式: word/pdf/printable"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="completed", comment="状态: generating/completed/failed"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败错误信息"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="更新时间"
    )

    # 关联
    user: Mapped["User"] = relationship(back_populates="exam_papers")
