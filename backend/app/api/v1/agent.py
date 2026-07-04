"""
<<<<<<< HEAD
AI Agent 路由 (PBI_04, PBI_12) — 对话、会话管理
=======
AI Agent 路由 (PBI_04, PBI_12)

端点:
- POST   /agent/chat               — 创建/继续对话 [SSE]
- GET    /agent/sessions           — 会话列表（分页）
- GET    /agent/sessions/{id}      — 获取历史消息
- DELETE /agent/sessions/{id}      — 删除会话
>>>>>>> main
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
<<<<<<< HEAD
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.orchestrator import agent_orchestrator
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import ChatReq, ChatSessionItem, ChatMessageItem
=======
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import ChatReq, ChatMessageItem, ChatSessionItem
>>>>>>> main
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.agent_service import AgentService

router = APIRouter()


<<<<<<< HEAD
@router.post("/chat", summary="创建/继续对话 [SSE]")
async def chat(
=======
# ================================================================
# POST /agent/chat — SSE 流式对话
# ================================================================

@router.post("/chat", summary="创建/继续对话 (SSE)")
async def agent_chat(
>>>>>>> main
    req: ChatReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """向 AI Agent 发送消息，SSE 流式返回思考链 + 回复内容"""
    service = AgentService(db)

    # 获取或创建会话
    session = await service.get_or_create_session(current_user.id, req.session_id)
    await db.commit()

    # 保存用户消息
    await service.save_message(session.id, "user", req.message)
    await db.commit()

    # 获取历史消息
    history_messages = await service.get_messages(session.id, current_user.id)
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages[:-1]  # 排除刚保存的用户消息（会在 orchestrator 中追加）
    ]

    async def event_stream():
        full_response = ""
        thought_chain = []
        try:
            async for event in agent_orchestrator.run_stream(
                session_id=session.id,
                user_message=req.message,
                history=history,
            ):
                if event["type"] == "thought":
                    thought_chain.append(event)
                elif event["type"] == "content":
                    full_response += event["chunk"]
                elif event["type"] == "done":
                    # 保存 AI 回复
                    await service.save_message(
                        session.id, "assistant", full_response,
                        thought_chain=thought_chain,
                    )
                    await db.commit()
                # SSE 格式输出
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session.id,
=======
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
>>>>>>> main
        },
    )


<<<<<<< HEAD
@router.get("/sessions", summary="会话列表")
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话会话列表（分页）"""
    service = AgentService(db)
    sessions, total = await service.list_sessions(current_user.id, page, page_size)
    return make_paginated_response(
        items=[
            ChatSessionItem(
                id=s.id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
            ).model_dump()
            for s in sessions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sessions/{session_id}", summary="获取历史消息")
=======
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
>>>>>>> main
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """获取指定会话的所有历史消息"""
    service = AgentService(db)
    messages = await service.get_messages(session_id, current_user.id)
    if not messages:
        # 检查会话是否存在
        from app.models.chat import ChatSession
        session = await db.get(ChatSession, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在", "detail": None},
            )
    return make_response(
        data=[
            ChatMessageItem(
                id=msg.id,
                session_id=msg.session_id,
                role=msg.role,
                content=msg.content,
                thought_chain=msg.thought_chain,
                tool_calls=msg.tool_calls,
                created_at=msg.created_at,
            ).model_dump()
            for msg in messages
        ]
    )

=======
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
>>>>>>> main

@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """删除指定会话及其所有消息"""
    service = AgentService(db)
    success = await service.delete_session(session_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在"},
        )
    await db.commit()
    return make_response(message="删除成功")
=======
    """删除指定会话及其所有消息（级联删除）"""
    service = AgentService(db)
    success = await service.delete_session(current_user.id, session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在或无权操作"},
        )

    return make_response(None, message="会话已删除")
>>>>>>> main
