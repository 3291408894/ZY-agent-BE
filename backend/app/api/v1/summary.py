"""
课文总结路由 (PBI_06) — 生成总结、历史记录
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.summary import GenerateSummaryReq, SummaryItem
from app.services.summary_service import SummaryService

router = APIRouter()


@router.post("/generate", summary="发起总结 [SSE]")
async def generate_summary(
    req: GenerateSummaryReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交课文内容，SSE 流式返回 AI 总结"""
    service = SummaryService(db)

    async def event_stream():
        async for event in service.generate_stream(
            user_id=current_user.id,
            source_type=req.source_type,
            content=req.content,
            mode=req.mode,
            file_id=req.file_id,
        ):
            if event["type"] == "done":
                await db.commit()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", summary="历史总结列表")
async def list_summaries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mode: str | None = Query(default=None, description="筛选模式: brief / detailed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有总结记录（分页，可按 mode 筛选）"""
    service = SummaryService(db)
    summaries, total = await service.list_summaries(current_user.id, page, page_size, mode)
    return make_paginated_response(
        items=[
            SummaryItem(
                id=s.id,
                source_type=s.source_type,
                source_content=s.source_content[:200] if s.source_content else "",
                summary_text=s.summary_text[:500] if s.summary_text else "",
                mode=s.mode,
                knowledge_points=s.knowledge_points or [],
                created_at=s.created_at,
            ).model_dump()
            for s in summaries
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{summary_id}", summary="查看总结详情")
async def get_summary(
    summary_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看指定总结的完整内容"""
    service = SummaryService(db)
    summary = await service.get_summary(summary_id, current_user.id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "总结记录不存在", "detail": None},
        )
    return make_response(
        data=SummaryItem(
            id=summary.id,
            source_type=summary.source_type,
            source_content=summary.source_content,
            summary_text=summary.summary_text,
            mode=summary.mode,
            knowledge_points=summary.knowledge_points or [],
            created_at=summary.created_at,
        ).model_dump()
    )


@router.delete("/{summary_id}", summary="删除总结")
async def delete_summary(
    summary_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定总结记录"""
    service = SummaryService(db)
    success = await service.delete_summary(summary_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "总结记录不存在", "detail": None},
        )
    await db.commit()
    return make_response(message="删除成功")
