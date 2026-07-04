"""
习题相关 Pydantic Schema (PBI_08, PBI_09, PBI_10)
"""

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


# --- 生成习题 ---
class GenerateExerciseReq(BaseModel):
    subject: str = Field(..., description="学科", examples=["语文"])
    grade: str = Field(..., description="年级", examples=["七年级"])
    knowledge_points: list[str] = Field(..., description="知识点列表")
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM)
    question_types: list[QuestionType] = Field(default=[QuestionType.CHOICE])
    count: int = Field(default=5, ge=1, le=50, description="生成数量")


class ExerciseItem(BaseModel):
    """生成阶段的习题（不含答案）"""
    id: str
    question: str
    question_type: str
    options: list[str] | None = None
    answer: str | None = None  # 生成阶段为 null
    analysis: str | None = None  # 生成阶段为 null
    difficulty: str
    knowledge_points: list[str] = []
    subject: str = ""
    grade: str = ""


# --- 批改 ---
class AnswerItem(BaseModel):
    exercise_id: str
    user_answer: str


class GradeReq(BaseModel):
    batch_id: str
    answers: list[AnswerItem]


class GradedItem(BaseModel):
    exercise_id: str
    is_correct: bool | None
    score: float
    correct_answer: str
    analysis: str | None = None
    error_reason: str | None = None
    related_knowledge: list[str] = []


class GradeResp(BaseModel):
    total_score: float
    correct_count: int
    total_count: int
    results: list[GradedItem]


# --- 批次 ---
class ExerciseBatchItem(BaseModel):
    id: str
    exercises: list[dict] = []
    grade_result: dict | None = None
    created_at: str = ""
