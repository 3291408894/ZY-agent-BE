"""
用户 & 学习档案模型 (PBI_01)
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    nickname: Mapped[str] = mapped_column(String(64), default="同学")
    grade: Mapped[str] = mapped_column(String(32), nullable=True)  # 如 "七年级"
    subjects: Mapped[list] = mapped_column(JSON, default=list)  # ["语文","数学"]
    textbook_version: Mapped[str] = mapped_column(String(64), nullable=True)  # "部编版"
    avatar_url: Mapped[str] = mapped_column(String(512), nullable=True)
    theme_preferences: Mapped[dict] = mapped_column(JSON, default=dict)  # {"fontSize":"medium","themeMode":"light","colorScheme":"eye-care","readingMode":false}

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    profile: Mapped["LearningProfile"] = relationship(back_populates="user", uselist=False)
    summaries: Mapped[list["Summary"]] = relationship(back_populates="user")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="user")
    exercises: Mapped[list["Exercise"]] = relationship(back_populates="user")
    exercise_attempts: Mapped[list["ExerciseAttempt"]] = relationship(back_populates="user")
    knowledge_graphs: Mapped[list["KnowledgeGraph"]] = relationship(back_populates="user")


class LearningProfile(Base):
    __tablename__ = "learning_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    total_study_time: Mapped[int] = mapped_column(Integer, default=0)  # 秒
    total_exercises: Mapped[int] = mapped_column(Integer, default=0)
    correct_rate: Mapped[float] = mapped_column(Float, default=0.0)
    weak_points: Mapped[list] = mapped_column(JSON, default=list)  # ["文言文阅读","二次函数"]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="profile")
