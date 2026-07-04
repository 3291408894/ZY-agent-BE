"""
AI Agent 路由 (PBI_04, PBI_12) — 对话、会话管理
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.orchestrator import agent_orchestrator
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import ChatReq, ChatSessionItem, ChatMessageItem
from app.schemas.common import ErrorCode, make_response
from app.services.agent_service import AgentService

router = APIRouter()


@router.post("/chat", summary="创建/继续对话 [SSE]")
async def chat(
    req: ChatReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
                    async with db.bind.connect() as conn:
                        from sqlalchemy.ext.asyncio import AsyncSession as AS
                        async with AS(conn) as new_db:
                            svc = AgentService(new_db)
                            await svc.save_message(
                                session.id, "assistant", full_response,
                                thought_chain=thought_chain,
                            )
                            await new_db.commit()
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
        },
    )


@router.get("/sessions", summary="会话列表")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话会话列表"""
    service = AgentService(db)
    sessions = await service.list_sessions(current_user.id)
    return make_response(
        data=[
            ChatSessionItem(
                id=s.id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
            ).model_dump()
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}", summary="获取历史消息")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
                detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "会话不存在"},
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


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
