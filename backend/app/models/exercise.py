"""
习题 & 作答记录模型 (PBI_08, PBI_09, PBI_10)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    subject: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(32))
    question_type: Mapped[str] = mapped_column(
        String(32)
    )  # choice / fill / short_answer / calculation / analysis
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 选择题选项
    answer: Mapped[str] = mapped_column(Text)  # 标准答案
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)  # 解题思路
    difficulty: Mapped[str] = mapped_column(String(16))  # easy / medium / hard
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(back_populates="exercises")
    attempts: Mapped[list["ExerciseAttempt"]] = relationship(back_populates="exercise")


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )

    user_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    graded_by: Mapped[str] = mapped_column(String(16), default="auto")  # auto / manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(back_populates="exercise_attempts")
    exercise: Mapped["Exercise"] = relationship(back_populates="attempts")
