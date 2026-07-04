"""
习题路由 (PBI_08, PBI_09, PBI_10) — 生成、提交、批改
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.exercise import GenerateExerciseReq, GradeReq
from app.services.exercise_service import ExerciseService

router = APIRouter()


@router.post("/generate", summary="生成习题 [SSE]")
async def generate_exercises(
    req: GenerateExerciseReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """根据学科/知识点/难度生成练习题，SSE 流式返回"""
    service = ExerciseService(db)

    async def event_stream():
        async for event in service.generate_stream(
            user_id=current_user.id,
            subject=req.subject,
            grade=req.grade,
            knowledge_points=req.knowledge_points,
            difficulty=req.difficulty.value,
            question_types=[qt.value for qt in req.question_types],
            count=req.count,
        ):
            if event["type"] == "done":
                await db.commit()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/grade", summary="提交作答/批改")
async def grade_answers(
    req: GradeReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交作答并自动批改"""
    service = ExerciseService(db)
    answers = [a.model_dump() for a in req.answers]
    result = await service.grade_answers(
        user_id=current_user.id,
        answers=answers,
        batch_id=req.batch_id,
    )
    await db.commit()
    return make_response(data=result)


@router.get("/history", summary="做题历史")
async def get_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取做题历史列表（按批次聚合）"""
    service = ExerciseService(db)
    items, total = await service.get_history(current_user.id, page, page_size)
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


@router.get("/batches/{batch_id}", summary="单次练习详情")
async def get_batch_detail(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看某个批次的详细作答"""
    service = ExerciseService(db)
    details = await service.get_batch_detail(batch_id, current_user.id)
    return make_response(data=details)


@router.delete("/batches/{batch_id}", summary="删除批次")
async def delete_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除某个批次的作答记录"""
    service = ExerciseService(db)
    deleted = await service.delete_batch(batch_id, current_user.id)
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "批次不存在"},
        )
    await db.commit()
    return make_response(message=f"已删除 {deleted} 条记录")
