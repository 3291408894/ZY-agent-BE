"""
习题路由 (PBI_08, PBI_09, PBI_10) — 生成、批改、历史、批次管理
"""

import asyncio
import json
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.exercise import (
    AnswerItem,
    GenerateExerciseReq,
    GradeReq,
    GradeResp,
)
from app.services.exercise_service import ExerciseService

router = APIRouter()

# ════════════════════════════════════════════════════════════════
# POST /exercises/generate — 生成习题 [SSE] (PBI_08)
# ════════════════════════════════════════════════════════════════


@router.post("/generate", summary="生成习题 (SSE)", tags=["习题"])
async def generate_exercises(
    req: GenerateExerciseReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    根据学科/年级/知识点/难度生成习题，SSE 流式逐题返回。

    做题模式 (mode=practice)：不返回 answer/analysis
    解析模式 (mode=review)：返回完整答案和解析
    """
    service = ExerciseService(db)
    is_practice = req.mode == "practice"

    try:
        batch_id, exercises = await service.generate(current_user.id, req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.LLM_SERVICE_ERROR,
                "message": f"习题生成失败：{e}",
            },
        )

    async def event_stream():
        try:
            for i, ex in enumerate(exercises):
                # 做题模式隐藏答案和解析
                exercise_data = {
                    "id": ex.id,
                    "question": ex.question,
                    "question_type": ex.question_type,
                    "options": ex.options,
                    "answer": None if is_practice else ex.answer,
                    "analysis": None if is_practice else ex.analysis,
                    "difficulty": ex.difficulty,
                    "knowledge_points": ex.knowledge_points,
                }
                yield {
                    "event": "exercise",
                    "data": json.dumps(
                        {
                            "type": "exercise",
                            "progress": {
                                "generated": i + 1,
                                "total": len(exercises),
                            },
                            "exercise": exercise_data,
                        },
                        ensure_ascii=False,
                    ),
                }
                # 逐题间隔，营造流式体验
                await asyncio.sleep(0.08)

            # 完成事件 — 返回全部习题摘要
            all_exercises = []
            for ex in exercises:
                all_exercises.append(
                    {
                        "id": ex.id,
                        "question": ex.question,
                        "question_type": ex.question_type,
                        "options": ex.options,
                        "answer": None if is_practice else ex.answer,
                        "analysis": None if is_practice else ex.analysis,
                        "difficulty": ex.difficulty,
                        "knowledge_points": ex.knowledge_points,
                    }
                )

            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "type": "done",
                        "batch_id": batch_id,
                        "exercises": all_exercises,
                    },
                    ensure_ascii=False,
                ),
            }
        except Exception:
            logger.error(f"SSE 流异常: {traceback.format_exc()}")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"type": "error", "message": "流式响应中断"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_stream())


# ════════════════════════════════════════════════════════════════
# POST /exercises/grade — 提交作答/批改 (PBI_10)
# ════════════════════════════════════════════════════════════════


@router.post(
    "/grade", response_model=GradeResp, summary="批改作答", tags=["习题"]
)
async def grade_answers(
    req: GradeReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    提交一套作答，由 LLM 自动批改并返回评分和纠错建议。
    """
    service = ExerciseService(db)
    try:
        result = await service.grade(current_user.id, req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": str(e)},
        )
    return result


# ════════════════════════════════════════════════════════════════
# GET /exercises/history — 做题历史（按批次分组）(PBI_09)
# ════════════════════════════════════════════════════════════════


@router.get("/history", summary="做题历史", tags=["习题"])
async def get_exercise_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    subject: str | None = Query(default=None, description="按学科筛选"),
    grade: str | None = Query(default=None, description="按年级筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """做题历史，按生成批次分组，最新在前。"""
    service = ExerciseService(db)
    data = await service.get_history(
        current_user.id,
        page=page,
        page_size=page_size,
        subject=subject,
        grade=grade,
    )
    return make_paginated_response(
        items=data["items"],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


# ════════════════════════════════════════════════════════════════
# GET /exercises/batches/{batch_id} — 批次详情
# ════════════════════════════════════════════════════════════════


@router.get(
    "/batches/{batch_id}", summary="批次详情（含作答）", tags=["习题"]
)
async def get_batch_detail(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看一个批次的完整习题列表和作答记录（解析模式）。"""
    service = ExerciseService(db)
    detail = await service.get_batch_detail(current_user.id, batch_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "批次不存在或无权访问",
            },
        )
    return make_response(detail)


# ════════════════════════════════════════════════════════════════
# DELETE /exercises/batches/{batch_id} — 删除批次
# ════════════════════════════════════════════════════════════════


@router.delete(
    "/batches/{batch_id}", summary="删除批次", tags=["习题"]
)
async def delete_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一个批次的所有习题（级联删除作答记录）。"""
    service = ExerciseService(db)
    deleted = await service.delete_batch(current_user.id, batch_id)
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "批次不存在或无权操作",
            },
        )
    return make_response({"deleted": deleted}, message="已删除")
