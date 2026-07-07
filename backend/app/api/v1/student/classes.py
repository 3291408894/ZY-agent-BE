"""
学生端 — 班级管理路由

端点:
    POST   /student/classes/join      — 通过邀请码加入班级
    GET    /student/classes           — 我加入的班级列表
    DELETE /student/classes/{id}/leave — 退出班级
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.classes import JoinClassReq
from app.schemas.common import ErrorCode, make_response
from app.services.class_service import ClassService

router = APIRouter()


@router.post("/join", status_code=201)
async def join_class(
    req: JoinClassReq,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """通过邀请码加入班级"""
    service = ClassService(db)
    try:
        result = await service.join_by_code(
            student_id=str(current_user.id),
            invite_code=req.invite_code,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": str(e)},
        )
    return make_response(data=result, message="加入成功")


@router.get("")
async def list_my_classes(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """我加入的班级列表"""
    service = ClassService(db)
    classes = await service.get_student_classes(student_id=str(current_user.id))
    return make_response(data={"classes": classes})


@router.delete("/{class_id}/leave")
async def leave_class(
    class_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """退出班级"""
    service = ClassService(db)
    left = await service.leave_class(class_id, str(current_user.id))
    if not left:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "未在该班级中"},
        )
    return make_response(message="已退出班级")
