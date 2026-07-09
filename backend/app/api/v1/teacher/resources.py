"""
教学资源库路由 (功能3) — 上传/下载/列表/搜索/收藏/删除
"""

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_teacher, get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.teaching_resource import (
    ALLOWED_EXTENSIONS,
    ResourceDetail,
    ResourceItem,
    ResourceUploadResp,
)
from app.schemas.class_resource import SendToClassRequest
from app.services.class_resource_service import ClassResourceService
from app.services.teaching_resource_service import TeachingResourceService

router = APIRouter()


# ============================================================
# 上传
# ============================================================

@router.post("/upload", summary="上传教学资源")
async def upload_resource(
    file: UploadFile,
    title: str = Form(..., description="资源标题"),
    subject: str = Form(..., description="学科"),
    grade: str = Form(..., description="适用年级"),
    resource_type: str = Form(..., description="资源类型: courseware/exam_paper/lesson_plan/other"),
    visibility: str = Form(default="public", description="可见性: public/private"),
    description: str | None = Form(default=None, description="资源描述"),
    tags: str | None = Form(default=None, description="标签，逗号分隔"),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    上传教学资源文件。

    支持格式: pdf, docx, pptx, xlsx, mp4, mp3, jpg/png/gif 等图片, txt, zip
    最大文件: 50MB
    """
    # 读取文件内容
    content = await file.read()

    # 解析 tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    service = TeachingResourceService(db)
    try:
        record = await service.upload(
            user_id=current_user.id,
            title=title,
            subject=subject,
            grade=grade,
            resource_type=resource_type,
            visibility=visibility,
            filename=file.filename or "unknown",
            content=content,
            description=description,
            tags=tag_list,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": str(e), "detail": None},
        )

    await db.commit()

    return make_response(
        data=ResourceUploadResp(
            id=record.id,
            uploader_id=record.uploader_id,
            title=record.title,
            description=record.description,
            subject=record.subject,
            grade=record.grade,
            resource_type=record.resource_type,
            file_type=record.file_type,
            file_name=record.file_name,
            file_size=record.file_size,
            file_ext=record.file_ext,
            visibility=record.visibility,
            tags=record.tags,
            created_at=record.created_at,
        ).model_dump(mode="json"),
        message="上传成功",
    )


# ============================================================
# 资源广场列表
# ============================================================

@router.get("", summary="资源广场列表")
async def list_resources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    subject: str | None = Query(default=None, description="学科筛选"),
    grade: str | None = Query(default=None, description="年级筛选"),
    resource_type: str | None = Query(default=None, description="资源类型筛选"),
    file_type: str | None = Query(default=None, description="文件类型筛选"),
    sort_by: str = Query(default="created_at", description="排序字段"),
    sort_order: str = Query(default="desc", description="排序方式: asc/desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    资源广场 — 浏览所有公开资源。

    支持关键词搜索、学科/年级/类型/文件格式筛选、多种排序。
    """
    service = TeachingResourceService(db)
    items, total = await service.list_resources(
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        subject=subject,
        grade=grade,
        resource_type=resource_type,
        file_type=file_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 我的资源
# ============================================================

@router.get("/my", summary="我的上传资源")
async def list_my_resources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    resource_type: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """我的上传资源列表（含私有资源）"""
    service = TeachingResourceService(db)
    items, total = await service.list_my_resources(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        resource_type=resource_type,
        visibility=visibility,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 我的收藏
# ============================================================

@router.get("/favorites", summary="我的收藏列表")
async def list_my_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户收藏的资源列表"""
    service = TeachingResourceService(db)
    items, total = await service.list_my_favorites(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return make_paginated_response(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# 筛选选项
# ============================================================

@router.get("/filter-options", summary="获取筛选选项")
async def get_filter_options(
    db: AsyncSession = Depends(get_db),
):
    """获取可用的筛选下拉选项（学科、年级、资源类型、文件类型）"""
    service = TeachingResourceService(db)
    options = await service.get_filter_options()
    return make_response(data=options)


# ============================================================
# 资源详情
# ============================================================

@router.get("/{resource_id}", summary="资源详情")
async def get_resource_detail(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取教学资源详情"""
    service = TeachingResourceService(db)
    detail = await service.get_detail(
        resource_id=resource_id,
        current_user_id=current_user.id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "资源不存在或无权查看", "detail": None},
        )
    return make_response(data=detail)


# ============================================================
# 下载
# ============================================================

@router.get("/{resource_id}/download", summary="下载资源文件")
async def download_resource(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载教学资源文件，自动记录下载日志并增加计数"""
    service = TeachingResourceService(db)
    result = await service.download(
        resource_id=resource_id,
        current_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "资源不存在或文件缺失", "detail": None},
        )

    file_path, file_name, file_ext = result
    await db.commit()

    # 构造 Content-Type
    media_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
        "zip": "application/zip",
        "txt": "text/plain",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "svg": "image/svg+xml",
    }

    # 处理文件名编码（支持中文）
    encoded_filename = quote(file_name)

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type_map.get(file_ext, "application/octet-stream"),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


# ============================================================
# 删除（软删除）
# ============================================================

@router.delete("/{resource_id}", summary="删除资源")
async def delete_resource(
    resource_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """软删除教学资源（仅上传者可操作）"""
    service = TeachingResourceService(db)
    success = await service.soft_delete(resource_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "资源不存在或无权操作", "detail": None},
        )
    await db.commit()
    return make_response(message="删除成功")


# ============================================================
# 发送到班级
# ============================================================

@router.post("/{resource_id}/send-to-class", summary="发送资源到班级")
async def send_resource_to_classes(
    resource_id: str,
    body: SendToClassRequest,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """将教学资源发送到指定班级（可多选）"""
    service = ClassResourceService(db)
    try:
        result = await service.send_to_classes(
            resource_id=resource_id,
            class_ids=body.class_ids,
            teacher_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PARAM_INVALID, "message": str(e), "detail": None},
        )

    await db.commit()

    msg_parts = []
    if result["success_count"] > 0:
        msg_parts.append(f"已发送到 {result['success_count']} 个班级")
    if result["skipped"]:
        msg_parts.append(f"{len(result['skipped'])} 个班级已分享过（{', '.join(result['skipped'])}）")
    if result["errors"]:
        msg_parts.append(f"{len(result['errors'])} 个班级发送失败")

    return make_response(data=result, message="；".join(msg_parts) if msg_parts else "操作完成")


# ============================================================
# 收藏/取消收藏
# ============================================================

@router.post("/{resource_id}/favorite", summary="切换收藏状态")
async def toggle_favorite(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收藏/取消收藏教学资源，返回当前收藏状态"""
    service = TeachingResourceService(db)
    try:
        result = await service.toggle_favorite(resource_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": str(e), "detail": None},
        )
    await db.commit()
    return make_response(
        data=result,
        message="已收藏" if result["is_favorited"] else "已取消收藏",
    )
