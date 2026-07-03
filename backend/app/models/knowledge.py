"""知识图谱 — SQLAlchemy 数据模型桩 (PBI_11)"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy import JSON

from app.core.database import Base


class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), default="")
    nodes = Column(JSON, default=list)
    edges = Column(JSON, default=list)
    source_type = Column(String(32), default="subject")
    created_at = Column(DateTime(timezone=True), nullable=False)
