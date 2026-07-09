"""
班级试卷分享模型 — 教师将试卷分享到班级
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClassExamPaper(Base):
    """班级试卷分享关联表"""

    __tablename__ = "class_exam_papers"
    __table_args__ = (
        UniqueConstraint("class_id", "exam_paper_id", name="uq_cep_class_paper"),
        Index("idx_cep_class_id", "class_id"),
        Index("idx_cep_exam_paper_id", "exam_paper_id"),
        {"comment": "班级试卷分享表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id", ondelete="CASCADE")
    )
    exam_paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_papers.id", ondelete="CASCADE")
    )
    shared_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), comment="分享教师ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    class_: Mapped["Class"] = relationship(back_populates="shared_exam_papers")
    exam_paper: Mapped["ExamPaper"] = relationship()
    sharer: Mapped["User"] = relationship()
