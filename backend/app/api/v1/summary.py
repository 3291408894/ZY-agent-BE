"""课文总结模块 — API 路由 (PBI_06)"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.summary import (
    GenerateSummaryRequest,
    SummaryListQuery,
    SummaryListResponse,
    SummaryDetailResponse,
    SummaryMode,
)
from app.services.summary_service import SummaryService

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# POST /summaries/generate — SSE 流式生成总结
# ═══════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_summary(
    req: GenerateSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成课文总结（SSE 流式响应）

    SSE 事件类型:
    - content:         总结文本增量
    - knowledge_points: 提取的知识点列表
    - done:            总结完成（含 summary_id）
    - error:           出错信息
    """
    service = SummaryService(db)

    async def event_stream():
        async for sse_line in service.generate_summary_stream(
            user_id=current_user.id,
            content=req.content,
            mode=req.mode,
        ):
            yield f"data: {sse_line}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


# ═══════════════════════════════════════════════════════════
# GET /summaries — 历史总结列表（分页）
# ═══════════════════════════════════════════════════════════

@router.get("", response_model=SummaryListResponse)
async def list_summaries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mode: SummaryMode | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取历史总结记录（分页）"""
    service = SummaryService(db)
    return await service.list_summaries(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        mode=mode,
    )


# ═══════════════════════════════════════════════════════════
# GET /summaries/{summary_id} — 查看详情
# ═══════════════════════════════════════════════════════════

@router.get("/{summary_id}", response_model=SummaryDetailResponse)
async def get_summary_detail(
    summary_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看单条总结的详情（含完整原文）"""
    service = SummaryService(db)
    result = await service.get_summary(current_user.id, summary_id)
    if not result:
        raise HTTPException(status_code=404, detail="总结记录不存在")
    return result


# ═══════════════════════════════════════════════════════════
# DELETE /summaries/{summary_id} — 删除
# ═══════════════════════════════════════════════════════════

@router.delete("/{summary_id}")
async def delete_summary(
    summary_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条总结记录"""
    service = SummaryService(db)
    deleted = await service.delete_summary(current_user.id, summary_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="总结记录不存在或无权操作")
    return {"code": 0, "message": "删除成功"}
