"""
作业管理路由 — 教师端 (功能5)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_teacher, get_db
from app.models.user import User
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    BatchGradeRequest,
    GradingRequest,
)
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.assignment_service import AssignmentService

router = APIRouter()


# ============================================================
# 布置作业
# ============================================================

@router.post("", summary="布置作业")
async def create_assignment(
    body: AssignmentCreate,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师在指定班级布置作业"""
    service = AssignmentService(db)
    data = await service.create_assignment(
        teacher_id=current_user.id,
        class_id=body.class_id,
        title=body.title,
        subject=body.subject,
        content=body.content.model_dump(),
        due_date=body.due_date,
        description=body.description,
        total_score=body.total_score,
        allow_late_submission=body.allow_late_submission,
    )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": ErrorCode.FORBIDDEN, "message": "无权在该班级布置作业，请确认班级归属", "detail": None},
        )
    await db.commit()
    return make_response(data=data, message="作业布置成功")


# ============================================================
# 作业列表
# ============================================================

@router.get("", summary="作业列表")
async def list_assignments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    class_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取教师布置的作业列表"""
    service = AssignmentService(db)
    items, total = await service.get_teacher_assignments(
        teacher_id=current_user.id,
        page=page,
        page_size=page_size,
        class_id=class_id,
        status=status,
        subject=subject,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 作业详情
# ============================================================

@router.get("/{assignment_id}", summary="作业详情")
async def get_assignment_detail(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取作业详情（含提交统计）"""
    service = AssignmentService(db)
    detail = await service.get_assignment_detail(assignment_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在", "detail": None},
        )
    return make_response(data=detail)


# ============================================================
# 修改作业
# ============================================================

@router.patch("/{assignment_id}", summary="修改作业")
async def update_assignment(
    assignment_id: str,
    body: AssignmentUpdate,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """修改作业（截止时间/说明等）"""
    service = AssignmentService(db)
    update_data = body.model_dump(exclude_unset=True)
    assignment = await service.update_assignment(assignment_id, current_user.id, **update_data)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在或无权修改", "detail": None},
        )
    await db.commit()
    return make_response(message="作业已更新")


# ============================================================
# 删除作业
# ============================================================

@router.delete("/{assignment_id}", summary="删除作业")
async def delete_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """删除作业（无提交记录时才能删除）"""
    service = AssignmentService(db)
    success = await service.delete_assignment(assignment_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在、无权删除或已有提交记录", "detail": None},
        )
    await db.commit()
    return make_response(message="作业已删除")


# ============================================================
# 提交列表
# ============================================================

@router.get("/{assignment_id}/submissions", summary="提交列表")
async def list_submissions(
    assignment_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="submitted/grading/graded/returned"),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取作业的提交列表"""
    service = AssignmentService(db)
    result = await service.get_submissions(
        assignment_id=assignment_id,
        teacher_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在或无权查看", "detail": None},
        )
    items, total = result
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 提交详情
# ============================================================

@router.get("/{assignment_id}/submissions/{submission_id}", summary="提交详情")
async def get_submission_detail(
    assignment_id: str,
    submission_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """查看单份提交详情（含学生作答内容）"""
    service = AssignmentService(db)
    detail = await service.get_submission_detail(assignment_id, submission_id, current_user.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "提交不存在或无权查看", "detail": None},
        )
    return make_response(data=detail)


# ============================================================
# 批改
# ============================================================

@router.post("/{assignment_id}/submissions/{submission_id}/grade", summary="批改作业")
async def grade_submission(
    assignment_id: str,
    submission_id: str,
    body: GradingRequest,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师手动评分或确认AI批改结果"""
    service = AssignmentService(db)
    result = await service.grade_submission(
        assignment_id=assignment_id,
        submission_id=submission_id,
        teacher_id=current_user.id,
        scores=[s.model_dump() for s in body.scores] if body.scores else None,
        teacher_feedback=body.teacher_feedback,
        confirm_ai_feedback=body.confirm_ai_feedback,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "提交不存在或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(data=result, message="批改完成")


# ============================================================
# 批量AI批改
# ============================================================

@router.post("/{assignment_id}/batch-grade", summary="批量AI批改")
async def batch_ai_grade(
    assignment_id: str,
    body: BatchGradeRequest | None = None,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """一键AI批改所有未批改提交"""
    service = AssignmentService(db)
    submission_ids = body.submission_ids if body else None
    results = await service.batch_ai_grade(
        assignment_id=assignment_id,
        teacher_id=current_user.id,
        submission_ids=submission_ids,
    )
    await db.commit()
    return make_response(data=results, message=f"批改完成：成功 {results['success']}，失败 {results['failed']}")


# ============================================================
# 退回重做
# ============================================================

@router.post("/{assignment_id}/submissions/{submission_id}/return", summary="退回重做")
async def return_submission(
    assignment_id: str,
    submission_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """退回学生提交，学生可重新作答"""
    service = AssignmentService(db)
    success = await service.return_submission(assignment_id, submission_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "提交不存在或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(message="已退回，学生可重新提交")


# ============================================================
# 作业统计
# ============================================================

@router.get("/{assignment_id}/stats", summary="作业统计")
async def get_assignment_stats(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取作业完成率、平均分、分数分布、每题正确率等统计数据"""
    service = AssignmentService(db)
    stats = await service.get_assignment_stats(assignment_id, current_user.id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在或无权查看", "detail": None},
        )
    return make_response(data=stats)


# ============================================================
# 一键提醒
# ============================================================

@router.post("/{assignment_id}/remind", summary="一键提醒未提交学生")
async def remind_unsubmitted(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取未提交学生列表"""
    service = AssignmentService(db)
    unsubmitted = await service.remind_unsubmitted(assignment_id, current_user.id)
    if unsubmitted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "作业不存在或无权操作", "detail": None},
        )
    return make_response(
        data={"unsubmitted_count": len(unsubmitted), "unsubmitted_student_ids": unsubmitted},
        message=f"还有 {len(unsubmitted)} 名学生未提交",
    )
