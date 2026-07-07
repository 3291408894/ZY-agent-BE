"""
AI Agent 相关 Pydantic Schema (PBI_04, PBI_12)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 请求
# ============================================================
class ChatReq(BaseModel):
    """对话请求"""
    session_id: str | None = Field(default=None, description="会话ID，null 则新建会话")
    message: str = Field(..., min_length=1, description="用户输入")


class UpdateSessionTitleReq(BaseModel):
    """修改会话标题请求"""
    title: str = Field(..., min_length=1, max_length=100, description="新标题")


# ============================================================
# 响应
# ============================================================
class ChatSessionItem(BaseModel):
    """会话列表项"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageItem(BaseModel):
    """消息项"""
    id: int
    session_id: str
    role: str  # user / assistant
    content: str
    thought_chain: list | None = None
    tool_calls: list | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetailResp(BaseModel):
    """会话详情（含消息列表）"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageItem]


class SessionListGroup(BaseModel):
    """按日期分组的会话列表"""
    label: str  # "今天" / "昨天" / "本周" / "更早"
    sessions: list[ChatSessionItem]
