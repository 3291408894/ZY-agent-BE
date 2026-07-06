"""
习题相关 Pydantic Schema (PBI_08, PBI_09, PBI_10)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    CHOICE = "choice"
    FILL = "fill"
    SHORT_ANSWER = "short_answer"
    CALCULATION = "calculation"
    ANALYSIS = "analysis"


# ── 生成习题 (PBI_08) ──────────────────────────────────────────


class GenerateExerciseReq(BaseModel):
    subject: str = Field(..., description="学科", examples=["语文"])
    grade: str = Field(..., description="年级", examples=["七年级"])
    knowledge_points: list[str] = Field(..., description="知识点列表")
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM)
    question_types: list[QuestionType] = Field(
        default=[QuestionType.CHOICE]
    )
    count: int = Field(default=5, ge=1, le=50, description="生成数量")
    mode: str = Field(
        default="practice",
        description="practice=做题模式(隐藏答案), review=解析模式(显示答案)",
    )


class ExerciseItem(BaseModel):
    """习题项 — 做题模式下 answer/analysis 为 null"""

    id: str
    question: str
    question_type: QuestionType
    options: list[str] | None = None
    answer: str | None = None  # 做题模式下为 null
    analysis: str | None = None  # 做题模式下为 null
    difficulty: Difficulty
    knowledge_points: list[str]


# ── 批改 (PBI_10) ──────────────────────────────────────────────


class AnswerItem(BaseModel):
    exercise_id: str
    user_answer: str


class GradeReq(BaseModel):
    batch_id: str | None = None
    answers: list[AnswerItem]


class GradedItem(BaseModel):
    exercise_id: str
    is_correct: bool
    score: float
    correct_answer: str
    analysis: str
    user_answer: str = ""
    error_reason: str | None = None
    related_knowledge: list[str] = []


class GradeResp(BaseModel):
    total_score: float
    correct_count: int
    total_count: int
    results: list[GradedItem]


# ── 历史记录 & 批次 (PBI_09) ───────────────────────────────────


class BatchHistoryItem(BaseModel):
    """历史列表中的批次摘要"""

    batch_id: str
    subject: str
    grade: str
    question_types: list[str]
    count: int
    created_at: str | None


class ExerciseDetail(BaseModel):
    """带作答记录的习题详情（解析模式用）"""

    id: str
    question: str
    question_type: QuestionType
    options: list[str] | None = None
    answer: str | None = None
    analysis: str | None = None
    difficulty: Difficulty
    knowledge_points: list[str]
    user_answer: str | None = None
    is_correct: bool | None = None
    score: float | None = None


class BatchDetail(BaseModel):
    """批次完整详情"""

    batch_id: str
    subject: str
    grade: str
    created_at: str | None
    exercises: list[ExerciseDetail]
