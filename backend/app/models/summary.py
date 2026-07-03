"""
课文总结模型 (PBI_06)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    source_type: Mapped[str] = mapped_column(String(16))  # text / file
    source_content: Mapped[str] = mapped_column(Text)  # 原文 或 文件ID引用
    summary_text: Mapped[str] = mapped_column(Text)  # 总结正文
    mode: Mapped[str] = mapped_column(String(16), default="detailed")  # brief / detailed
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list)  # 提取的知识点
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(back_populates="summaries")
