"""
AI Agent 相关 Pydantic Schema (PBI_04, PBI_12)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# --- 对话 ---
class ChatReq(BaseModel):
    session_id: str | None = Field(default=None, description="会话ID，null 则新建会话")
    message: str = Field(..., min_length=1, description="用户输入")


class ChatSessionItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageItem(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    thought_chain: list | None = None
    tool_calls: list | None = None
    created_at: datetime
