"""智能教案生成模块 — Pydantic 请求/响应模型 (PBI_LP)"""

from pydantic import BaseModel, Field
from datetime import datetime


# ═══════════════════════════════════════════════════════════
# 嵌套模型
# ═══════════════════════════════════════════════════════════

class LessonPlanSection(BaseModel):
    """教案结构化分段"""
    title: str = Field(..., description="段落标题，如'教学目标'、'教学过程'")
    content: str = Field(..., description="段落内容")


# ═══════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════

class GenerateLessonPlanRequest(BaseModel):
    """发起教案生成请求 (POST /lesson-plans/generate)"""
    subject: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="学科，如'语文'、'数学'、'英语'"
    )
    grade: str = Field(
        ...,
        min_length=1,
        max_length=16,
        description="年级，如'四年级'、'七年级'"
    )
    textbook_version: str = Field(
        default="",
        max_length=64,
        description="教材版本，如'部编版'、'人教版'"
    )
    unit_chapter: str = Field(
        default="",
        max_length=128,
        description="单元/章节，如'第三单元 第九课《古诗三首》'"
    )
    class_hours: int = Field(
        default=1,
        ge=1,
        le=10,
        description="课时数"
    )
    teaching_objectives: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="教学目标描述"
    )
    requirements: str | None = Field(
        default=None,
        max_length=1000,
        description="特殊要求（可选）"
    )
    resource_id: str | None = Field(
        default=None,
        description="关联的教学资源库文件ID（可选，选中后AI将参考该文件内容生成教案）"
    )


class LessonPlanListQuery(BaseModel):
    """教案列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


# ═══════════════════════════════════════════════════════════
# 响应模型
# ═══════════════════════════════════════════════════════════

class LessonPlanItem(BaseModel):
    """教案列表项（文本截断）"""
    id: str
    title: str
    subject: str
    grade: str
    textbook_version: str
    unit_chapter: str
    class_hours: int
    plan_content: str = Field(..., description="教案正文（截断展示）")
    created_at: datetime


class LessonPlanDetailResponse(BaseModel):
    """教案详情响应（含完整内容）"""
    id: str
    title: str
    subject: str
    grade: str
    textbook_version: str
    unit_chapter: str
    class_hours: int
    teaching_objectives: str
    requirements: str | None = None
    plan_content: str = Field(..., description="完整教案正文")
    sections: list[LessonPlanSection] = Field(default_factory=list)
    created_at: datetime


class LessonPlanListResponse(BaseModel):
    """分页列表响应"""
    items: list[LessonPlanItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════
# SSE 事件类型
# ═══════════════════════════════════════════════════════════

class SSELessonPlanContentEvent(BaseModel):
    """SSE: 教案内容流式推送"""
    type: str = Field(default="content")
    chunk: str = Field(..., description="增量文本片段")


class SSELessonPlanDoneEvent(BaseModel):
    """SSE: 教案生成完成"""
    type: str = Field(default="done")
    lesson_plan_id: str
    title: str
