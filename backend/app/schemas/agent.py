"""
AI Agent 相关 Pydantic Schema (PBI_04, PBI_12)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ================================================================
# 请求
# ================================================================

class ChatReq(BaseModel):
    """对话请求"""
    session_id: str | None = Field(
        default=None, description="会话ID，为 null 时自动创建新会话"
    )
    message: str = Field(..., min_length=1, max_length=5000, description="用户输入的消息")


# ================================================================
# 响应
# ================================================================

class ChatSessionItem(BaseModel):
    """会话列表项"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageItem(BaseModel):
    """消息项"""
    id: int
    session_id: str
    role: str  # user / assistant
    content: str
    thought_chain: list[dict] | None = None  # PBI_12: 思考链步骤
    tool_calls: list[dict] | None = None     # PBI_12: 工具调用记录
    created_at: datetime


# ================================================================
# SSE 事件类型（供前端参考）
# ================================================================

class SSEThoughtEvent(BaseModel):
    """思考链事件"""
    type: str = "thought"
    step: int
    title: str
    content: str


class SSEContentEvent(BaseModel):
    """文本块事件"""
    type: str = "content"
    chunk: str


class SSEToolStartEvent(BaseModel):
    """工具调用开始事件"""
    type: str = "tool_start"
    tool_name: str
    step: int


class SSEToolResultEvent(BaseModel):
    """工具执行结果事件"""
    type: str = "tool_result"
    tool_name: str
    result: str


class SSEDoneEvent(BaseModel):
    """对话完成事件"""
    type: str = "done"
    session_id: str
    usage: dict
    thought_chain: list[dict] | None = None
    tool_calls: list[dict] | None = None


class SSEErrorEvent(BaseModel):
    """错误事件"""
    type: str = "error"
    message: str
