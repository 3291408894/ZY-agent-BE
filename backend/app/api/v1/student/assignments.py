"""
作业管理路由 — 学生端 (功能5)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.assignment import SubmissionCreate
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.assignment_service import AssignmentService

router = APIRouter()


# ============================================================
# 我的作业列表
# ============================================================

@router.get("", summary="我的作业列表")
async def list_my_assignments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="pending/submitted/graded/returned"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前学生的作业列表（按班级分组，显示提交状态）"""
    service = AssignmentService(db)
    items, total = await service.get_student_assignments(
        student_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 作业详情（题目内容）
# ============================================================

@router.get("/{assignment_id}", summary="作业详情")
async def get_assignment_detail(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生查看作业详情（含题目内容）"""
    service = AssignmentService(db)
    detail = await service.get_student_assignment_detail(assignment_id, current_user.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在或你不在该班级中", "detail": None},
        )
    return make_response(data=detail)


# ============================================================
# 提交作业
# ============================================================

@router.post("/{assignment_id}/submit", summary="提交作业")
async def submit_assignment(
    assignment_id: str,
    body: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生提交作业"""
    service = AssignmentService(db)
    result = await service.submit_assignment(
        assignment_id=assignment_id,
        student_id=current_user.id,
        content=body.content.model_dump(),
        attachments=body.attachments,
    )
    if result != "ok":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": result, "detail": None},
        )
    await db.commit()
    return make_response(message="作业提交成功")


# ============================================================
# 我的提交与批改结果
# ============================================================

@router.get("/{assignment_id}/my-submission", summary="我的提交")
async def get_my_submission(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看我的提交和批改结果"""
    service = AssignmentService(db)
    submission = await service.get_my_submission(assignment_id, current_user.id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "你尚未提交该作业", "detail": None},
        )
    return make_response(data=submission)
