"""
AI Agent 路由 (PBI_04, PBI_12) — 对话、会话管理

TODO: Sprint 1 实现
"""

from fastapi import APIRouter

router = APIRouter()

# POST   /agent/chat               — 创建/继续对话 [SSE]
# GET    /agent/sessions           — 会话列表
# GET    /agent/sessions/{id}       — 获取历史消息
# DELETE /agent/sessions/{id}       — 删除会话
