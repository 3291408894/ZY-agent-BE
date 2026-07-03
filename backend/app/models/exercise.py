"""习题 — SQLAlchemy 数据模型桩 (PBI_08/09/10)"""

from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy import JSON

from app.core.database import Base


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    subject = Column(String(32), default="")
    grade = Column(String(32), default="")
    question_type = Column(String(32), default="")
    question = Column(Text, default="")
    options = Column(JSON, default=list)
    answer = Column(Text, default="")
    analysis = Column(Text, default="")
    difficulty = Column(String(16), default="medium")
    knowledge_points = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    exercise_id = Column(String(36), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    user_answer = Column(Text, default="")
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    graded_by = Column(String(16), default="auto")
    created_at = Column(DateTime(timezone=True), nullable=False)
