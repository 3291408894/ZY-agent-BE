"""
班级资源分享模型 — 教师将教学资源分享到班级
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


class ClassResource(Base):
    """班级资源分享关联表"""

    __tablename__ = "class_resources"
    __table_args__ = (
        UniqueConstraint("class_id", "resource_id", name="uq_cr_class_resource"),
        Index("idx_cr_class_id", "class_id"),
        Index("idx_cr_resource_id", "resource_id"),
        {"comment": "班级资源分享表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id", ondelete="CASCADE")
    )
    resource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teaching_resources.id", ondelete="CASCADE")
    )
    shared_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), comment="分享教师ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    class_: Mapped["Class"] = relationship(back_populates="shared_resources")
    resource: Mapped["TeachingResource"] = relationship(back_populates="shared_classes")
    sharer: Mapped["User"] = relationship()
