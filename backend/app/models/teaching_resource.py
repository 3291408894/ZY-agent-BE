"""
教学资源库模型 — 资源主表、收藏表、下载日志表 (功能3)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TeachingResource(Base):
    __tablename__ = "teaching_resources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    uploader_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(50), index=True)
    grade: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str] = mapped_column(
        String(30), index=True, comment="courseware/exam_paper/lesson_plan/other"
    )
    file_type: Mapped[str] = mapped_column(
        String(20), comment="pdf/docx/pptx/xlsx/mp4/image/txt/zip/mp3"
    )
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(BigInteger, comment="文件大小(字节)")
    file_ext: Mapped[str] = mapped_column(String(10))

    download_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    visibility: Mapped[str] = mapped_column(
        String(20), default="public", comment="public/private"
    )
    is_recommended: Mapped[bool] = mapped_column(default=False)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active/deleted/reviewing"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # 关系
    uploader: Mapped["User"] = relationship(back_populates="teaching_resources")
    favorites: Mapped[list["ResourceFavorite"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    download_logs: Mapped[list["ResourceDownloadLog"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tr_created", "created_at"),
        {"comment": "教学资源库"},
    )


class ResourceFavorite(Base):
    __tablename__ = "resource_favorites"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("teaching_resources.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="resource_favorites")
    resource: Mapped["TeachingResource"] = relationship(back_populates="favorites")

    __table_args__ = (
        {"comment": "资源收藏"},
    )


class ResourceDownloadLog(Base):
    __tablename__ = "resource_download_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("teaching_resources.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="resource_download_logs")
    resource: Mapped["TeachingResource"] = relationship(back_populates="download_logs")

    __table_args__ = (
        {"comment": "资源下载日志"},
    )
