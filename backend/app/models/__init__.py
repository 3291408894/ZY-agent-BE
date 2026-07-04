"""
数据模型包 — 导入所有模型以便 Alembic 自动发现
"""

from app.core.database import Base

# 模型导入（Alembic 需要在此导入以检测表）
from app.models.user import User, LearningProfile, RefreshToken, PasswordResetToken
from app.models.chat import ChatSession, ChatMessage
from app.models.file import UploadedFile
from app.models.exercise import Exercise, ExerciseBatch, ExerciseAttempt
from app.models.knowledge import KnowledgeGraph
from app.models.summary import Summary

__all__ = [
    "Base",
    "User",
    "LearningProfile",
<<<<<<< HEAD
    "RefreshToken",
    "PasswordResetToken",
=======
    "Summary",
>>>>>>> main
    "ChatSession",
    "ChatMessage",
    "UploadedFile",
    "Exercise",
    "ExerciseBatch",
    "ExerciseAttempt",
    "KnowledgeGraph",
]
