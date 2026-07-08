"""
班级资源路由 — 学生端：查看班级共享资源 + 保存到知识库
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.class_resource_service import ClassResourceService

router = APIRouter()


# ============================================================
# 班级资源列表
# ============================================================

@router.get("/classes/{class_id}/resources", summary="班级资源列表")
async def list_class_resources(
    class_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生查看班级已分享的资源列表（需已加入该班级）"""
    service = ClassResourceService(db)
    try:
        # 验证学生属于该班级
        await service._verify_student_in_class(class_id, current_user.id)
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


# ============================================================
# 保存资源到知识库
# ============================================================

@router.post("/classes/{class_id}/resources/{resource_id}/save-to-knowledge", summary="保存到知识库")
async def save_resource_to_knowledge(
    class_id: str,
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    将班级共享资源保存到学生的知识库。
    系统会将资源文件复制到学生的上传文件目录，之后可在知识图谱页面基于该文件生成图谱。
    """
    service = ClassResourceService(db)
    try:
        result = await service.save_to_knowledge(
            class_id=class_id,
            resource_id=resource_id,
            student_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": str(e), "detail": None},
        )

    await db.commit()
    return make_response(
        data=result,
        message=f"已保存「{result['filename']}」到知识库，可在知识图谱页面查看",
    )
