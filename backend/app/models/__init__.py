"""数据模型注册 — 供 Alembic 自动发现"""

from app.models.user import User           # noqa: F401
from app.models.summary import Summary     # noqa: F401
from app.models.chat import ChatSession, ChatMessage  # noqa: F401
from app.models.file import UploadedFile   # noqa: F401
from app.models.exercise import Exercise, ExerciseAttempt  # noqa: F401
from app.models.knowledge import KnowledgeGraph  # noqa: F401
