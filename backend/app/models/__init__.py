"""
数据模型包 — 导入所有模型以便 Alembic 自动发现
"""

from app.core.database import Base

# 模型导入（Alembic 需要在此导入以检测表）
from app.models.user import User, LearningProfile
from app.models.chat import ChatSession, ChatMessage
from app.models.file import UploadedFile
from app.models.exercise import Exercise, ExerciseAttempt
from app.models.knowledge import KnowledgeGraph
from app.models.summary import Summary
from app.models.teaching_resource import TeachingResource, ResourceFavorite, ResourceDownloadLog
from app.models.classes import Class, ClassStudent
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.lesson_plan import LessonPlan
from app.models.exam_paper import ExamPaper
from app.models.class_resource import ClassResource

__all__ = [
    "Base",
    "User",
    "LearningProfile",
    "Summary",
    "ChatSession",
    "ChatMessage",
    "UploadedFile",
    "Exercise",
    "ExerciseAttempt",
    "KnowledgeGraph",
    "TeachingResource",
    "ResourceFavorite",
    "ResourceDownloadLog",
    "Class",
    "ClassStudent",
    "Assignment",
    "AssignmentSubmission",
    "LessonPlan",
    "ExamPaper",
    "ClassResource",
]
