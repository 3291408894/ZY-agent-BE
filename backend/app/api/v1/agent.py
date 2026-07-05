"""
AI Agent 路由 (PBI_04, PBI_12)

端点:
- POST   /agent/chat               — 创建/继续对话 [SSE]
- GET    /agent/sessions           — 会话列表（分页）
- GET    /agent/sessions/{id}      — 获取历史消息
- DELETE /agent/sessions/{id}      — 删除会话
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import ChatReq, ChatMessageItem, ChatSessionItem
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.agent_service import AgentService

router = APIRouter()


# ================================================================
# POST /agent/chat — SSE 流式对话
# ================================================================

@router.post("/chat", summary="创建/继续对话 (SSE)")
async def agent_chat(
    req: ChatReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    发起 AI Agent 对话，使用 Server-Sent Events (SSE) 流式返回结果。

    SSE 事件类型:
    - thought: 思考步骤（PBI_12 可视化）
    - content: AI 回复文本块
    - tool_start: 开始调用工具
    - tool_result: 工具执行结果
    - done: 对话完成（含 session_id）
    - error: 错误信息

    请求示例:
    ```json
    {
      "session_id": null,
      "message": "帮我总结《背影》这篇课文的主要内容"
    }
    ```
    """
    service = AgentService(db)

    async def event_generator():
        try:
            async for event in service.chat_stream(
                user_id=current_user.id,
                session_id=req.session_id,
                message=req.message,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[Agent API] SSE 流异常 | user={current_user.id} | error={e}")
            error_event = json.dumps(
                {"type": "error", "message": f"服务器内部错误: {str(e)}"},
                ensure_ascii=False,
            )
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


# ================================================================
# GET /agent/sessions — 会话列表
# ================================================================

@router.get("/sessions", summary="获取会话列表")
async def list_sessions(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话会话列表，按更新时间倒序排列"""
    service = AgentService(db)
    sessions, total = await service.list_sessions(current_user.id, page, page_size)

    items = [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]

    return make_paginated_response(items, total, page, page_size)


# ================================================================
# GET /agent/sessions/{session_id} — 会话历史消息
# ================================================================

@router.get("/sessions/{session_id}", summary="获取会话历史消息")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定会话的所有历史消息（含思考链和工具调用记录）"""
    service = AgentService(db)
    messages = await service.get_session_messages(current_user.id, session_id)

    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在或无权访问"},
        )

    items = [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "thought_chain": m.thought_chain,
            "tool_calls": m.tool_calls,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]

    return make_response(items)


# ================================================================
# DELETE /agent/sessions/{session_id} — 删除会话
# ================================================================

@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定会话及其所有消息（级联删除）"""
    service = AgentService(db)
    success = await service.delete_session(current_user.id, session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在或无权操作"},
        )

    return make_response(None, message="会话已删除")
