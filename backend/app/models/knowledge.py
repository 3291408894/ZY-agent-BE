"""
知识图谱模型 (PBI_11)
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(255))
    nodes: Mapped[list] = mapped_column(JSON, default=list)  # 图谱节点 [{id, label, type, x, y}]
    edges: Mapped[list] = mapped_column(JSON, default=list)  # 图谱边 [{source, target, relation}]
    source_type: Mapped[str] = mapped_column(String(16))  # subject / chapter / file
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(back_populates="knowledge_graphs")
