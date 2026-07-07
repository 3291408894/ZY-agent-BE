"""
教师端 — 班级管理路由

端点:
    POST   /teacher/classes                        — 创建班级
    GET    /teacher/classes                        — 我的班级列表
    GET    /teacher/classes/{id}                   — 班级详情
    GET    /teacher/classes/{id}/roster             — 花名册
    DELETE /teacher/classes/{id}/students/{student_id} — 移除学生
    POST   /teacher/classes/{id}/regenerate-code   — 重新生成邀请码
    PATCH  /teacher/classes/{id}/archive           — 归档班级
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_teacher, get_db
from app.models.user import User
from app.schemas.classes import ClassCreateReq
from app.schemas.common import ErrorCode, make_response
from app.services.class_service import ClassService

router = APIRouter()


@router.post("", status_code=201)
async def create_class(
    req: ClassCreateReq,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """创建班级 — 自动生成 8 位邀请码"""
    service = ClassService(db)
    cls = await service.create_class(
        teacher_id=str(current_user.id),
        name=req.name,
        grade=req.grade,
        subject=req.subject,
        description=req.description,
    )
    return make_response(
        data={
            "id": cls.id,
            "name": cls.name,
            "grade": cls.grade,
            "subject": cls.subject,
            "description": cls.description,
            "invite_code": cls.invite_code,
            "student_count": cls.student_count,
            "status": cls.status,
            "created_at": cls.created_at.isoformat(),
            "updated_at": cls.updated_at.isoformat(),
        },
        message="班级创建成功",
    )


@router.get("")
async def list_classes(
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """我的班级列表（按更新时间倒序）"""
    service = ClassService(db)
    classes = await service.get_teacher_classes(teacher_id=str(current_user.id))
    items = [
        {
            "id": c.id,
            "name": c.name,
            "grade": c.grade,
            "subject": c.subject,
            "description": c.description,
            "invite_code": c.invite_code,
            "student_count": c.student_count,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in classes
    ]
    return make_response(data={"classes": items})


@router.get("/{class_id}")
async def get_class_detail(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """班级详情"""
    service = ClassService(db)
    cls = await service.get_class_detail(class_id, str(current_user.id))
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权访问"},
        )
    return make_response(
        data={
            "id": cls.id,
            "name": cls.name,
            "grade": cls.grade,
            "subject": cls.subject,
            "description": cls.description,
            "invite_code": cls.invite_code,
            "student_count": cls.student_count,
            "status": cls.status,
            "created_at": cls.created_at.isoformat(),
            "updated_at": cls.updated_at.isoformat(),
        }
    )


@router.get("/{class_id}/roster")
async def get_roster(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """班级花名册（学生列表 + 加入时间）"""
    service = ClassService(db)
    roster = await service.get_roster(class_id, str(current_user.id))
    if roster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权访问"},
        )
    return make_response(data={"roster": roster})


@router.delete("/{class_id}/students/{student_id}")
async def remove_student(
    class_id: str,
    student_id: str,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """移除学生"""
    service = ClassService(db)
    removed = await service.remove_student(class_id, str(current_user.id), student_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级或学生不存在"},
        )
    return make_response(message="学生已移除")


@router.post("/{class_id}/regenerate-code")
async def regenerate_invite_code(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """重新生成邀请码（旧码立即失效）"""
    service = ClassService(db)
    new_code = await service.regenerate_invite_code(class_id, str(current_user.id))
    if new_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或已归档"},
        )
    return make_response(data={"invite_code": new_code}, message="邀请码已重新生成")


@router.patch("/{class_id}/archive")
async def archive_class(
    class_id: str,
    current_user: User = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """归档班级"""
    service = ClassService(db)
    cls = await service.archive_class(class_id, str(current_user.id))
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "班级不存在或无权访问"},
        )
    return make_response(data={"status": cls.status}, message="班级已归档")
