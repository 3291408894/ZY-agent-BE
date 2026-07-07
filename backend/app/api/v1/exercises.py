"""
习题路由 (PBI_08, PBI_09, PBI_10) — 生成、提交、批改
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.exercise import (
    GradeReq,
    GenerateExerciseReq,
)
from app.services.exercise_service import ExerciseService

router = APIRouter()


# ================================================================
# POST /exercises/generate — SSE 流式生成习题
# ================================================================

@router.post("/generate", summary="生成习题 (SSE)")
async def generate_exercises(
    req: GenerateExerciseReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI 生成练习题，使用 Server-Sent Events (SSE) 流式返回结果。

    SSE 事件类型:
    - progress:  生成进度 {type, generated, total}
    - exercise:  单道习题 {type, exercise: {...}}
    - done:      生成完成 {type, batch_id}
    - error:     错误信息 {type, message}

    请求示例:
    ```json
    {
      "subject": "语文",
      "grade": "七年级",
      "knowledge_points": ["修辞手法", "文章主旨"],
      "difficulty": "medium",
      "question_types": ["choice", "short_answer"],
      "count": 5
    }
    ```
    """
    service = ExerciseService(db)

    async def event_stream():
        async for sse_line in service.generate_exercises_stream(
            user_id=current_user.id,
            subject=req.subject,
            grade=req.grade,
            knowledge_points=req.knowledge_points,
            difficulty=req.difficulty.value,
            question_types=[qt.value for qt in req.question_types],
            count=req.count,
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


# ================================================================
# POST /exercises/grade — 提交作答并批改
# ================================================================

@router.post("/grade", summary="提交作答并批改")
async def grade_exercises(
    req: GradeReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交学生的作答，AI 自动批改并返回评分和解析"""
    service = ExerciseService(db)
    result = await service.grade_answers(
        user_id=current_user.id,
        batch_id=req.batch_id or "unknown",
        answers=[a.model_dump() for a in req.answers],
    )
    return make_response(data=result, message="批改完成")


# ================================================================
# GET /exercises/history — 做题历史
# ================================================================

@router.get("/history", summary="做题历史")
async def get_exercise_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的做题历史（分页）"""
    service = ExerciseService(db)
    items, total = await service.get_history(current_user.id, page, page_size)
    return make_paginated_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ================================================================
# GET /exercises/batches/{batch_id} — 单次练习详情
# ================================================================

@router.get("/batches/{batch_id}", summary="练习详情")
async def get_exercise_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看单次练习的详情（含习题和作答记录）"""
    service = ExerciseService(db)
    detail = await service.get_batch_detail(current_user.id, batch_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "练习记录不存在",
                "detail": None,
            },
        )
    return make_response(data=detail)


# ================================================================
# DELETE /exercises/batches/{batch_id} — 删除练习记录
# ================================================================

@router.delete("/batches/{batch_id}", summary="删除练习记录")
async def delete_exercise_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定批次的练习记录"""
    service = ExerciseService(db)
    success = await service.delete_batch(current_user.id, batch_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "练习记录不存在或无权操作",
                "detail": None,
            },
        )
    return make_response(message="删除成功")
