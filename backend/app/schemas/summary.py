"""课文总结模块 — Pydantic 请求/响应模型 (PBI_06)"""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


<<<<<<< HEAD
class KnowledgePoint(BaseModel):
    """知识点"""
    name: str
    category: str


class GenerateSummaryReq(BaseModel):
    source_type: str = Field(..., description="text 或 file")
    content: str = Field(..., description="课文原文")
    mode: str = Field(default="detailed", description="brief 或 detailed")
    file_id: str | None = None
=======
# ═══════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════

class SummaryMode(str, Enum):
    """总结模式"""
    BRIEF = "brief"          # 精简版：主旨 + 段落概要
    DETAILED = "detailed"    # 详细版：主旨 + 段落 + 考点 + 写作手法


class SummarySourceType(str, Enum):
    """总结来源类型"""
    TEXT = "text"            # 手动输入/粘贴文本
    FILE = "file"            # 上传文件（第二阶段集成）


# ═══════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════

class GenerateSummaryRequest(BaseModel):
    """发起总结请求 (POST /summaries/generate)"""
    source_type: SummarySourceType = Field(
        default=SummarySourceType.TEXT,
        description="来源类型：text=手动输入，file=文件引用"
    )
    content: str = Field(
        default="",
        min_length=10,
        max_length=50000,
        description="课文原文内容（source_type=text 时必填）"
    )
    mode: SummaryMode = Field(
        default=SummaryMode.DETAILED,
        description="总结模式：brief=精简版，detailed=详细版"
    )
    file_id: str | None = Field(
        default=None,
        description="文件ID（source_type=file 时传入）"
    )


class SummaryListQuery(BaseModel):
    """历史总结列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    mode: SummaryMode | None = Field(default=None, description="按模式筛选")


# ═══════════════════════════════════════════════════════════
# 响应模型
# ═══════════════════════════════════════════════════════════

class KnowledgePoint(BaseModel):
    """知识点"""
    name: str = Field(..., description="知识点名称")
    category: str = Field(default="", description="知识点分类，如'文言实词'、'写作手法'")
>>>>>>> main


class SummaryItem(BaseModel):
    """单条总结记录"""
    id: str
<<<<<<< HEAD
    source_type: str
    source_content: str
    summary_text: str
    mode: str
    knowledge_points: list[KnowledgePoint] = []
=======
    source_type: SummarySourceType
    source_content: str = Field(..., description="课文原文（截断展示）")
    summary_text: str = Field(..., description="总结正文")
    mode: SummaryMode
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
>>>>>>> main
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
