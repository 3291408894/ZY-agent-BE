"""课文总结模块 — Pydantic 请求/响应模型 (PBI_06)"""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SummaryMode(str, Enum):
    """总结模式"""
    BRIEF = "brief"
    DETAILED = "detailed"


class SummarySourceType(str, Enum):
    """总结来源类型"""
    TEXT = "text"
    FILE = "file"


class KnowledgePoint(BaseModel):
    """知识点"""
    name: str
    category: str


class GenerateSummaryReq(BaseModel):
    source_type: str = Field(..., description="text 或 file")
    content: str = Field(..., description="课文原文")
    mode: str = Field(default="detailed", description="brief 或 detailed")
    file_id: str | None = None


class SummaryItem(BaseModel):
    """单条总结记录"""
    id: str
    source_type: str
    source_content: str
    summary_text: str
    mode: str
    knowledge_points: list[KnowledgePoint] = []
    created_at: datetime


class SummaryDetailResponse(BaseModel):
    """总结详情响应（含完整原文）"""
    id: str
    source_type: SummarySourceType
    source_content: str = Field(..., description="完整课文原文")
    summary_text: str = Field(..., description="总结正文")
    mode: SummaryMode
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    created_at: datetime


class SummaryListResponse(BaseModel):
    """分页列表响应"""
    items: list[SummaryItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════
# SSE 事件类型
# ═══════════════════════════════════════════════════════════

class SSESummaryContentEvent(BaseModel):
    """SSE: 总结内容流式推送"""
    type: str = Field(default="content")
    chunk: str = Field(..., description="增量文本片段")


class SSEKnowledgePointsEvent(BaseModel):
    """SSE: 知识点提取完成"""
    type: str = Field(default="knowledge_points")
    points: list[KnowledgePoint]


class SSESummaryDoneEvent(BaseModel):
    """SSE: 总结生成完成"""
    type: str = Field(default="done")
    summary_id: str
    mode: SummaryMode
