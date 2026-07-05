"""用户 — SQLAlchemy 数据模型 (PBI_01)"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键 UUID")
    email = Column(String(255), unique=True, index=True, nullable=True, comment="邮箱")
    phone = Column(String(32), unique=True, index=True, nullable=True, comment="手机号")
    hashed_password = Column(String(255), nullable=False, comment="bcrypt 密码哈希")
    nickname = Column(String(64), default="", comment="昵称")
    grade = Column(String(32), default="", comment="年级")
    subjects = Column(JSON, default=list, comment="学科偏好列表")
    textbook_version = Column(String(64), default="", comment="教材版本")
    avatar_url = Column(String(512), default="", comment="头像 URL")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # 关联
    summaries = relationship("Summary", back_populates="user", cascade="all, delete-orphan")
