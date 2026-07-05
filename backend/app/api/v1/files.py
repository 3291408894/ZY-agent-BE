"""
文件管理路由 (PBI_05) — 上传、解析、状态查询
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.file import FileItem, FileUploadResp
from app.services.file_service import FileService

router = APIRouter()


@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile,
    auto_parse: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传学习资料文件，支持 9 种格式"""
    # 校验文件大小
    content = await file.read()
    max_size = settings.max_file_size_bytes
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.FILE_SIZE_EXCEEDED,
                "message": f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)",
                "detail": None,
            },
        )

    service = FileService(db)
    try:
        record = await service.upload(current_user.id, file.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.FILE_FORMAT_UNSUPPORTED, "message": str(e), "detail": None},
        )

    # 保存 file_id，避免 commit 后 ORM 对象过期
    file_id = record.id
    await db.commit()

    # 自动解析
    if auto_parse:
        try:
            await service.parse_file(file_id)
            await db.commit()
        except Exception:
            pass  # 解析失败不影响上传成功

    # 重新查询，拿到最新数据
    record = await service.get_file(file_id, current_user.id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": ErrorCode.INTERNAL_ERROR, "message": "文件保存后查询失败", "detail": None},
        )

    return make_response(
        data=FileUploadResp(
            id=record.id,
            user_id=record.user_id,
            filename=record.filename,
            file_type=record.file_type,
            file_size=record.file_size,
            storage_path=record.storage_path,
            parse_status=record.parse_status,
            parsed_content=record.parsed_content,
            created_at=record.created_at,
        ).model_dump(mode="json"),
        message="上传成功",
    )


@router.get("", summary="文件列表")
async def list_files(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    file_type: str | None = Query(default=None, description="筛选文件类型"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户上传的所有文件（分页）"""
    service = FileService(db)
    files, total = await service.list_files(current_user.id, page, page_size, file_type)
    return make_paginated_response(
        items=[
            FileItem(
                id=f.id,
                filename=f.filename,
                file_type=f.file_type,
                file_size=f.file_size,
                parse_status=f.parse_status,
                created_at=f.created_at,
            ).model_dump(mode="json")
            for f in files
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{file_id}/status", summary="解析状态")
async def get_file_status(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询文件的解析状态和内容"""
    service = FileService(db)
    record = await service.get_file(file_id, current_user.id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在", "detail": None},
        )
    return make_response(
        data={
            "id": record.id,
            "user_id": record.user_id,
            "filename": record.filename,
            "file_type": record.file_type,
            "file_size": record.file_size,
            "storage_path": record.storage_path,
            "parse_status": record.parse_status,
            "parsed_content": record.parsed_content,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
    )


@router.post("/{file_id}/reparse", summary="重新解析")
async def reparse_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新触发文件解析，返回完整文件对象"""
    service = FileService(db)
    result = await service.reparse(file_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在", "detail": None},
        )
    await db.commit()

    # 读取更新后的记录
    record = await service.get_file(file_id, current_user.id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": ErrorCode.INTERNAL_ERROR, "message": "重新解析后查询失败", "detail": None},
        )
    return make_response(
        data=FileUploadResp(
            id=record.id,
            user_id=record.user_id,
            filename=record.filename,
            file_type=record.file_type,
            file_size=record.file_size,
            storage_path=record.storage_path,
            parse_status=record.parse_status,
            parsed_content=record.parsed_content,
            created_at=record.created_at,
        ).model_dump(mode="json"),
        message="已提交重新解析",
    )


@router.delete("/{file_id}", summary="删除文件")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定文件及其解析结果"""
    service = FileService(db)
    success = await service.delete_file(file_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在", "detail": None},
        )
    await db.commit()
    return make_response(message="删除成功")
