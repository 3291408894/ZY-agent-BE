"""
课文总结相关 Pydantic Schema (PBI_06)
"""

from datetime import datetime

from pydantic import BaseModel, Field


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
    id: str
    source_type: str
    source_content: str
    summary_text: str
    mode: str
    knowledge_points: list[KnowledgePoint] = []
    created_at: datetime
