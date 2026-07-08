"""
班级管理路由 — 教师端 (功能4)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_teacher, get_db
from app.models.user import User
from app.schemas.classes import ClassCreate, ClassUpdate
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.class_service import ClassService
from app.services.class_resource_service import ClassResourceService

router = APIRouter()


# ============================================================
# 创建班级
# ============================================================

@router.post("", summary="创建班级")
async def create_class(
    body: ClassCreate,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师创建新班级，系统自动生成8位邀请码"""
    service = ClassService(db)
    cls_data = await service.create_class(
        teacher_id=current_user.id,
        name=body.name,
        grade=body.grade,
        subject=body.subject,
        description=body.description,
    )
    await db.commit()
    return make_response(data=cls_data, message="班级创建成功")


# ============================================================
# 我的班级列表
# ============================================================

@router.get("", summary="我的班级列表")
async def list_classes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="active/archived"),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取当前教师创建的所有班级"""
    service = ClassService(db)
    items, total = await service.get_teacher_classes(
        teacher_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 班级详情
# ============================================================

@router.get("/{class_id}", summary="班级详情")
async def get_class_detail(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取班级详情（含花名册）"""
    service = ClassService(db)
    detail = await service.get_class_detail(class_id, current_user.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权查看", "detail": None},
        )
    return make_response(data=detail)


# ============================================================
# 花名册
# ============================================================

@router.get("/{class_id}/roster", summary="花名册")
async def get_roster(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取班级花名册（学生列表+加入时间）"""
    service = ClassService(db)
    roster = await service.get_roster(class_id, current_user.id)
    if not roster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权查看", "detail": None},
        )
    return make_response(data={
        "class_id": roster["id"],
        "class_name": roster["name"],
        "student_count": roster["student_count"],
        "students": roster["students"],
    })


# ============================================================
# 移除学生
# ============================================================

@router.delete("/{class_id}/students/{student_id}", summary="移除学生")
async def remove_student(
    class_id: str,
    student_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师移除班级中的学生"""
    service = ClassService(db)
    success = await service.remove_student(class_id, student_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级或学生不存在，或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(message="已移除该学生")


# ============================================================
# 重新生成邀请码
# ============================================================

@router.post("/{class_id}/regenerate-code", summary="重新生成邀请码")
async def regenerate_invite_code(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """重新生成邀请码（旧码立即失效）"""
    service = ClassService(db)
    new_code = await service.regenerate_invite_code(class_id, current_user.id)
    if not new_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(data={"invite_code": new_code}, message="邀请码已重新生成")


# ============================================================
# 归档班级
# ============================================================

@router.patch("/{class_id}/archive", summary="归档班级")
async def archive_class(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """归档班级（归档后不可新增作业，但仍可查看历史数据）"""
    service = ClassService(db)
    success = await service.archive_class(class_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(message="班级已归档")


# ============================================================
# 班级资源列表
# ============================================================

@router.get("/{class_id}/resources", summary="班级资源列表")
async def get_class_resources(
    class_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师查看班级已分享的资源列表"""
    service = ClassResourceService(db)
    try:
        items, total = await service.list_class_resources(
            class_id=class_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": str(e), "detail": None},
        )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)
