"""
AI Agent 路由 (PBI_04, PBI_12) — 对话、会话管理

端点:
    POST   /agent/chat                     — 创建/继续对话 [SSE]
    GET    /agent/sessions                 — 会话列表（按日期分组）
    GET    /agent/sessions/{session_id}     — 会话详情（含历史消息）
    PATCH  /agent/sessions/{session_id}/title — 修改会话标题
    DELETE /agent/sessions/{session_id}     — 删除会话
"""

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.ai.agent.orchestrator import agent_orchestrator
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import ChatReq, UpdateSessionTitleReq
from app.schemas.common import ErrorCode, make_response
from app.services.agent_service import AgentService

router = APIRouter()


# ============================================================
# SSE 对话
# ============================================================

@router.post("/chat")
async def chat(
    req: ChatReq,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    创建/继续对话 (PBI_04) — Server-Sent Events 流式响应

    SSE 事件格式:
        data: {"type":"thought","step":1,"title":"需求分析","content":"..."}
        data: {"type":"content","chunk":"响应文本片段"}
        data: {"type":"done","session_id":"uuid","usage":{"total_chars":1234}}
        data: {"type":"error","message":"错误信息"}
    """
    user_id = str(current_user.id)
    service = AgentService(db)

    # 1. 获取或创建会话
    if req.session_id:
        session = await service._get_owned_session(req.session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": ErrorCode.RESOURCE_NOT_FOUND,
                    "message": "会话不存在或无权访问",
                },
            )
        is_new_session = False
    else:
        session = await service.create_session(user_id)
        is_new_session = True

    # 2. 保存用户消息
    await service.save_message(
        session_id=session.id,
        role="user",
        content=req.message,
    )

    # 3. 构建历史消息上下文
    history = await _build_history(service, session.id)

    async def event_stream() -> AsyncIterator[str]:
        """SSE 事件生成器"""
        full_response = ""
        thought_chain: list[dict] = []
        tool_calls: list[dict] = []

        try:
            async for event in agent_orchestrator.run_stream(
                session_id=session.id,
                user_message=req.message,
                history=history,
            ):
                # 收集完整响应
                if event.get("type") == "content":
                    full_response += event.get("chunk", "")
                elif event.get("type") == "thought":
                    thought_chain.append(event)

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 4. 保存 AI 回复
            if full_response:
                await service.save_message(
                    session_id=session.id,
                    role="assistant",
                    content=full_response,
                    thought_chain=thought_chain if thought_chain else None,
                    tool_calls=tool_calls if tool_calls else None,
                )

            # 5. 新会话自动生成标题
            if is_new_session:
                await service._auto_title(session.id)

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'AI 服务暂时不可用: {str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 会话管理
# ============================================================

@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """会话列表 — 按日期分组返回（今天/昨天/本周/更早）"""
    service = AgentService(db)
    groups = await service.get_sessions(user_id=str(current_user.id))
    return make_response(data={"groups": groups})


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取会话详情 — 包含全部历史消息"""
    service = AgentService(db)
    detail = await service.get_session_detail(
        session_id=session_id,
        user_id=str(current_user.id),
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "会话不存在或无权访问",
            },
        )
    return make_response(data=detail)


@router.patch("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    req: UpdateSessionTitleReq,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """修改会话标题（用户自定义）"""
    service = AgentService(db)
    session = await service.update_session_title(
        session_id=session_id,
        user_id=str(current_user.id),
        title=req.title,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "会话不存在或无权访问",
            },
        )
    return make_response(
        data={"id": session.id, "title": session.title},
        message="标题已更新",
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除会话（级联删除所有消息）"""
    service = AgentService(db)
    deleted = await service.delete_session(
        session_id=session_id,
        user_id=str(current_user.id),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "会话不存在或无权访问",
            },
        )
    return make_response(message="会话已删除")


# ============================================================
# 内部
# ============================================================

async def _build_history(service: AgentService, session_id: str) -> list[dict]:
    """构建 LLM 上下文用的历史消息列表（仅取 role/content，排除刚存入的最新用户消息）"""
    from sqlalchemy import select

    from app.models.chat import ChatMessage

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    result = await service.db.execute(stmt)
    all_messages = result.scalars().all()

    # 排除刚存入的那条用户消息（最后一条），避免 LLM 收到重复 user 消息
    history_messages = all_messages[:-1] if len(all_messages) > 1 else []
    recent = history_messages[-20:]
    return [{"role": m.role, "content": m.content} for m in recent]
