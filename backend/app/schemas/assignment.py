"""
作业管理系统 Schema — 布置/提交/批改/统计 (功能5)
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


# ============================================================
# 枚举
# ============================================================

class AssignmentStatusEnum(str):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SubmissionStatusEnum(str):
    SUBMITTED = "submitted"
    GRADING = "grading"
    GRADED = "graded"
    RETURNED = "returned"


# ============================================================
# 作业内容结构
# ============================================================

class ObjectiveQuestion(BaseModel):
    """客观题"""
    number: int = Field(..., description="题号")
    stem: str = Field(..., description="题干")
    options: list[str] = Field(default_factory=list, description="选项列表")
    answer: str = Field(..., description="正确答案")
    score: int = Field(default=0, description="分值")
    explanation: str | None = Field(default=None, description="解析")


class SubjectiveQuestion(BaseModel):
    """主观题"""
    number: int = Field(..., description="题号")
    stem: str = Field(..., description="题干")
    answer: str = Field(..., description="参考答案")
    score: int = Field(default=0, description="分值")
    scoring_rubric: str | None = Field(default=None, description="评分标准")


class AssignmentSection(BaseModel):
    """作业内容分区"""
    type: str = Field(..., description="objective / subjective")
    title: str = Field(..., description="分区标题")
    questions: list[ObjectiveQuestion | SubjectiveQuestion] = Field(default_factory=list)


class AssignmentContent(BaseModel):
    """作业内容完整结构"""
    format: str = Field(default="mixed", description="mixed / objective_only / subjective_only")
    sections: list[AssignmentSection] = Field(default_factory=list)


# ============================================================
# 布置作业请求
# ============================================================

class AssignmentCreate(BaseModel):
    """布置作业请求"""
    class_id: str = Field(..., description="所属班级ID")
    title: str = Field(..., min_length=1, max_length=200, description="作业标题")
    description: str | None = Field(default=None, description="作业说明/要求")
    subject: str = Field(..., min_length=1, max_length=50, description="学科")
    content: AssignmentContent = Field(..., description="作业内容")
    total_score: int | None = Field(default=None, ge=0, description="总分")
    due_date: datetime = Field(..., description="截止时间")
    allow_late_submission: bool = Field(default=False, description="是否允许迟交")


class AssignmentUpdate(BaseModel):
    """修改作业"""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: datetime | None = None
    allow_late_submission: bool | None = None


# ============================================================
# 作业响应
# ============================================================

class AssignmentItem(BaseModel):
    """作业列表项"""
    id: str
    class_id: str
    class_name: str = ""
    title: str
    subject: str
    total_score: int | None
    due_date: datetime
    allow_late_submission: bool
    submission_count: int
    graded_count: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentDetail(BaseModel):
    """作业详情"""
    id: str
    class_id: str
    class_name: str = ""
    teacher_id: str
    title: str
    description: str | None
    subject: str
    content: dict
    total_score: int | None
    due_date: datetime
    allow_late_submission: bool
    submission_count: int
    graded_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 提交相关
# ============================================================

class StudentAnswer(BaseModel):
    """学生作答"""
    question_number: int
    answer: str


class SubmissionContent(BaseModel):
    """提交内容"""
    answers: list[StudentAnswer]


class SubmissionCreate(BaseModel):
    """提交作业请求"""
    content: SubmissionContent = Field(..., description="作答内容")
    attachments: list[dict] | None = Field(default=None, description="附件列表")


# ============================================================
# AI 批改反馈
# ============================================================

class StepFeedback(BaseModel):
    """分步反馈"""
    step: str = ""
    correct: bool = True
    comment: str = ""


class AIFeedback(BaseModel):
    """AI 批改反馈"""
    score: int = 0
    overall_comment: str = ""
    step_feedback: list[StepFeedback] = Field(default_factory=list)
    error_analysis: str | None = None
    suggested_score: int = 0


class QuestionScore(BaseModel):
    """逐题评分"""
    question_number: int
    score: int = Field(default=0, ge=0, description="该题得分")


class GradingRequest(BaseModel):
    """教师批改请求"""
    scores: list[QuestionScore] | None = Field(default=None, description="逐题评分列表")
    teacher_feedback: str | None = Field(default=None, description="教师评语")
    confirm_ai_feedback: bool = Field(default=False, description="确认AI批改结果")


class BatchGradeRequest(BaseModel):
    """批量AI批改请求"""
    submission_ids: list[str] | None = Field(default=None, description="指定提交ID列表，不传则批改所有未批改的")


# ============================================================
# 提交响应
# ============================================================

class SubmissionItem(BaseModel):
    """提交列表项"""
    id: str
    assignment_id: str
    student_id: str
    student_name: str = ""
    student_nickname: str = ""
    score: int | None
    status: str
    submitted_at: datetime | None
    graded_at: datetime | None

    class Config:
        from_attributes = True


class SubmissionDetail(BaseModel):
    """提交详情"""
    id: str
    assignment_id: str
    student_id: str
    student_name: str = ""
    content: dict
    attachments: list | None
    score: int | None
    ai_feedback: dict | None
    teacher_feedback: str | None
    teacher_id: str | None
    status: str
    submitted_at: datetime | None
    graded_at: datetime | None

    class Config:
        from_attributes = True


# ============================================================
# 统计
# ============================================================

class AssignmentStats(BaseModel):
    """作业统计"""
    total_students: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    completion_rate: float = 0.0
    average_score: float | None = None
    score_distribution: dict[str, int] = Field(default_factory=dict)
    question_stats: list[dict] = Field(default_factory=list)


# ============================================================
# 作业列表查询
# ============================================================

class AssignmentListParams(BaseModel):
    """作业列表查询参数"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    class_id: str | None = None
    status: str | None = None
    subject: str | None = None


class SubmissionListParams(BaseModel):
    """提交列表查询参数"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: str | None = None
