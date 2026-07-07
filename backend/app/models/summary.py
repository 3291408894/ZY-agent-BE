"""课文总结 — SQLAlchemy 数据模型 (PBI_06)"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Summary(Base):
    """课文总结记录表"""

    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键 UUID"
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="所属用户",
    )
    source_type: Mapped[str] = mapped_column(
        String(16), default="text", comment="来源类型: text / file"
    )
    source_content: Mapped[str] = mapped_column(Text, comment="课文原文")
    summary_text: Mapped[str] = mapped_column(Text, comment="总结正文")
    mode: Mapped[str] = mapped_column(
        String(16), default="detailed", comment="总结模式: brief / detailed"
    )
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list, comment="提取的知识点列表")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="创建时间"
    )

    # 关联
    user: Mapped["User"] = relationship(back_populates="summaries")
