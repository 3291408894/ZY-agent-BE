"""智能教案生成模块 — API 路由 (PBI_LP)"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.lesson_plan import (
    GenerateLessonPlanRequest,
    LessonPlanListResponse,
    LessonPlanDetailResponse,
)
from app.services.lesson_plan_service import LessonPlanService

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# POST /lesson-plans/generate — SSE 流式生成教案
# ═══════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_lesson_plan(
    req: GenerateLessonPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成教案（SSE 流式响应）

    SSE 事件类型:
    - content:         教案内容增量
    - done:            教案生成完成（含 lesson_plan_id 和 title）
    - error:           出错信息
    """
    # 检查 LLM 配置
    if not settings.LLM_API_KEY:
        async def error_stream():
            import json
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI 服务未配置。请在 .env 文件中设置 LLM_API_KEY'})}\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    service = LessonPlanService(db)

    async def event_stream():
        async for sse_line in service.generate_stream(
            request=req,
            user_id=current_user.id,
        ):
            yield f"data: {sse_line}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════
# GET /lesson-plans — 历史教案列表（分页）
# ═══════════════════════════════════════════════════════════

@router.get("", response_model=LessonPlanListResponse)
async def list_lesson_plans(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取历史教案记录（分页）"""
    service = LessonPlanService(db)
    return await service.list_lesson_plans(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


# ═══════════════════════════════════════════════════════════
# GET /lesson-plans/{lesson_plan_id} — 查看详情
# ═══════════════════════════════════════════════════════════

@router.get("/{lesson_plan_id}", response_model=LessonPlanDetailResponse)
async def get_lesson_plan_detail(
    lesson_plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看单条教案的详情（含完整教案内容）"""
    service = LessonPlanService(db)
    result = await service.get_lesson_plan(current_user.id, lesson_plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="教案记录不存在")
    return result


# ═══════════════════════════════════════════════════════════
# DELETE /lesson-plans/{lesson_plan_id} — 删除
# ═══════════════════════════════════════════════════════════

@router.delete("/{lesson_plan_id}")
async def delete_lesson_plan(
    lesson_plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条教案记录"""
    service = LessonPlanService(db)
    deleted = await service.delete_lesson_plan(current_user.id, lesson_plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="教案记录不存在或无权操作")
    return {"code": 0, "message": "删除成功"}
