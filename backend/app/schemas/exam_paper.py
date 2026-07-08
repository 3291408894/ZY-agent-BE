"""
试卷生成器 — Pydantic Schema (功能2)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


# ============================================================
# 枚举
# ============================================================


class ExamType(str, Enum):
    """考试类型"""
    UNIT_TEST = "unit_test"
    MIDTERM = "midterm"
    FINAL = "final"


class ExamPaperStatus(str, Enum):
    """试卷生成状态"""
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportFormat(str, Enum):
    """导出格式"""
    WORD = "word"
    PDF = "pdf"
    PRINTABLE = "printable"


# ============================================================
# 题型配置
# ============================================================


class QuestionTypeConfig(BaseModel):
    """单种题型配置"""
    type: str = Field(..., description="题型名称，如：选择题、填空题、简答题、计算题、综合题")
    count: int = Field(..., ge=1, le=50, description="题目数量")
    score_per: int = Field(..., ge=1, le=100, description="每题分值")
    subtotal: int = Field(..., ge=1, description="小计分数")


# ============================================================
# 请求
# ============================================================


class ExamPaperGenerateRequest(BaseModel):
    """试卷生成请求"""
    title: str = Field(..., min_length=1, max_length=200, description="试卷标题")
    subject: str = Field(..., min_length=1, max_length=50, description="学科")
    grade: str = Field(..., min_length=1, max_length=50, description="年级")
    exam_type: ExamType = Field(..., description="考试类型")
    total_score: int = Field(..., ge=1, le=300, description="总分")
    difficulty_ratio: dict[str, int] = Field(
        ...,
        description='难度配比，如 {"easy":30,"medium":50,"hard":20}，总和必须为100',
    )
    question_structure: list[QuestionTypeConfig] = Field(
        ..., min_length=1, max_length=10, description="题型分布"
    )
    focus_instruction: str | None = Field(
        default=None, max_length=500, description="补充说明/重点关注考点"
    )
    resource_id: str | None = Field(
        default=None,
        description="关联的教学资源库文件ID（可选，选中后AI将参考该文件内容生成试卷）"
    )

    @model_validator(mode="after")
    def validate_difficulty_ratio(self):
        """校验难度配比总和为100"""
        total = sum(self.difficulty_ratio.values())
        if total != 100:
            raise ValueError(f"难度配比总和必须为100，当前为{total}")
        allowed_keys = {"easy", "medium", "hard"}
        if set(self.difficulty_ratio.keys()) != allowed_keys:
            raise ValueError(f"难度配比必须包含 easy/medium/hard 三个键")
        return self

    @model_validator(mode="after")
    def validate_total_score(self):
        """校验题型小计与总分一致"""
        subtotal_sum = sum(q.subtotal for q in self.question_structure)
        for q in self.question_structure:
            if q.count * q.score_per != q.subtotal:
                raise ValueError(
                    f"题型'{q.type}'小计({q.subtotal})与数量×分值({q.count}×{q.score_per}={q.count * q.score_per})不一致"
                )
        if subtotal_sum != self.total_score:
            raise ValueError(f"题型小计总和({subtotal_sum})与总分({self.total_score})不一致")
        return self


class ExamPaperExportRequest(BaseModel):
    """导出请求"""
    format: ExportFormat = Field(default=ExportFormat.WORD, description="导出格式")


# ============================================================
# 响应
# ============================================================


class ExamPaperContentHeader(BaseModel):
    """试卷头部信息"""
    title: str
    subject: str
    grade: str
    exam_type: str
    total_score: int
    duration_minutes: int = 120
    instructions: str = ""


class ExamPaperQuestion(BaseModel):
    """单道试题"""
    number: int
    stem: str
    question_type: str
    options: list[str] | None = None  # 选择题的选项
    answer: str
    score: int
    analysis: str = ""  # 解析
    knowledge_points: list[str] = []


class ExamPaperSection(BaseModel):
    """试卷大题（如：一、选择题）"""
    title: str
    instructions: str = ""
    questions: list[ExamPaperQuestion]


class ExamPaperContent(BaseModel):
    """试卷正文"""
    header: ExamPaperContentHeader
    sections: list[ExamPaperSection]
    answer_key: list[dict] = []  # 参考答案
    scoring_guide: str = ""  # 评分标准


class ExamPaperAnswerSheet(BaseModel):
    """答题卡"""
    paper_id: str
    title: str
    student_info: dict = Field(
        default_factory=lambda: {"name": "", "class": "", "student_id": ""}
    )
    sections: list[dict] = []


class ExamPaperItem(BaseModel):
    """试卷列表项"""
    id: str
    title: str
    subject: str
    grade: str
    exam_type: ExamType
    total_score: int
    status: ExamPaperStatus
    question_count: int = 0  # 总题数
    created_at: datetime

    class Config:
        from_attributes = True


class ExamPaperDetail(BaseModel):
    """试卷详情"""
    id: str
    user_id: str
    title: str
    subject: str
    grade: str
    exam_type: ExamType
    total_score: int
    difficulty_ratio: dict
    question_structure: list[dict]
    content: ExamPaperContent
    answer_sheet: dict | None = None
    export_url: str | None = None
    export_format: str | None = None
    status: ExamPaperStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExamPaperListResponse(BaseModel):
    """试卷分页列表响应"""
    items: list[ExamPaperItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================
# SSE 事件类型
# ============================================================


class SSEEventType(str, Enum):
    """SSE事件类型"""
    THINKING = "thinking"  # 思考状态
    CONTENT = "content"  # 内容增量
    PROGRESS = "progress"  # 进度
    DONE = "done"  # 完成
    ERROR = "error"  # 错误
