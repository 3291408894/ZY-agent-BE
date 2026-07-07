"""
班级管理路由 — 学生端 (功能4)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.classes import JoinClassRequest
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.class_service import ClassService

router = APIRouter()


# ============================================================
# 通过邀请码加入班级
# ============================================================

@router.post("/join", summary="加入班级")
async def join_class(
    body: JoinClassRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生通过邀请码加入班级"""
    service = ClassService(db)

    # 先确认班级信息
    class_info = await service.get_class_by_invite_code(body.invite_code)
    if not class_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "邀请码无效或班级已归档", "detail": None},
        )

    # 执行加入
    result = await service.join_class(current_user.id, body.invite_code)
    if result == "already_joined":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": ErrorCode.USER_EXISTS, "message": "你已在该班级中", "detail": None},
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "加入失败，邀请码无效", "detail": None},
        )

    await db.commit()
    return make_response(data=class_info, message="加入班级成功")


# ============================================================
# 确认邀请码（查询班级信息）
# ============================================================

@router.get("/check-invite/{invite_code}", summary="查询邀请码")
async def check_invite_code(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生输入邀请码后，确认班级信息再决定是否加入"""
    service = ClassService(db)
    class_info = await service.get_class_by_invite_code(invite_code)
    if not class_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "邀请码无效或班级已归档", "detail": None},
        )
    return make_response(data=class_info)


# ============================================================
# 我的班级列表
# ============================================================

@router.get("", summary="我的班级列表")
async def list_my_classes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前学生加入的班级列表"""
    service = ClassService(db)
    items, total = await service.get_student_classes(
        student_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 退出班级
# ============================================================

@router.delete("/{class_id}/leave", summary="退出班级")
async def leave_class(
    class_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生主动退出班级"""
    service = ClassService(db)
    success = await service.leave_class(class_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或你未加入该班级", "detail": None},
        )
    await db.commit()
    return make_response(message="已退出班级")
