"""
数据模型包 — 导入所有模型以便 Alembic 自动发现
"""

from app.core.database import Base

# 模型导入（Alembic 需要在此导入以检测表）
from app.models.user import User, LearningProfile
from app.models.chat import ChatSession, ChatMessage
from app.models.summary import Summary
from app.models.file import UploadedFile
from app.models.exercise import Exercise, ExerciseAttempt
from app.models.knowledge import KnowledgeGraph
from app.models.classes import Class, ClassStudent

__all__ = [
    "Base",
    "User",
    "LearningProfile",
    "ChatSession",
    "ChatMessage",
    "Summary",
    "UploadedFile",
    "Exercise",
    "ExerciseAttempt",
    "KnowledgeGraph",
    "Class",
    "ClassStudent",
]
