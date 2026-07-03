"""课文总结 — SQLAlchemy 数据模型 (PBI_06)"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Summary(Base):
    """课文总结记录表"""

    __tablename__ = "summaries"

    id = Column(String(36), primary_key=True, comment="主键 UUID")
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属用户",
    )
    source_type = Column(
        String(16), default="text", nullable=False, comment="来源类型: text / file"
    )
    source_content = Column(Text, nullable=False, comment="课文原文")
    summary_text = Column(Text, nullable=False, comment="总结正文")
    mode = Column(
        String(16), default="detailed", nullable=False, comment="总结模式: brief / detailed"
    )
    knowledge_points = Column(JSON, default=list, comment="提取的知识点列表")
    created_at = Column(
        DateTime(timezone=True), nullable=False, comment="创建时间"
    )

    # 关联
    user = relationship("User", back_populates="summaries")
