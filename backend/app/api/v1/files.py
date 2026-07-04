"""
文件管理路由 (PBI_05) — 上传、解析、状态查询、删除

端点:
    POST   /files/upload          — 上传文件
    GET    /files                 — 文件列表（分页）
    GET    /files/{file_id}/status — 解析状态
    POST   /files/{file_id}/reparse — 重新解析
    DELETE /files/{file_id}       — 删除文件
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.file import ALLOWED_FILE_TYPES
from app.services.file_service import FileFormatError, FileService, FileSizeExceededError

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(..., description="上传文件"),
    auto_parse: bool = Form(default=True, description="是否自动解析"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    上传文件 (PBI_05)

    支持格式: txt / md / pdf / docx / csv / json / html / xml / yaml
    文件大小上限: 50MB（由配置 MAX_FILE_SIZE_MB 控制）
    """
    # 1. 快速格式校验（提前返回友好错误）
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供文件名",
        )

    suffix = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.FILE_FORMAT_UNSUPPORTED,
                "message": f"不支持的文件格式: .{suffix}，支持: {', '.join(sorted(ALLOWED_FILE_TYPES))}",
            },
        )

    # 2. 调用 Service
    service = FileService(db)
    try:
        record = await service.upload(
            user_id=str(current_user.id),
            file=file,
            auto_parse=auto_parse,
        )
    except FileSizeExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.FILE_SIZE_EXCEEDED,
                "message": str(e),
            },
        )
    except FileFormatError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.FILE_FORMAT_UNSUPPORTED,
                "message": str(e),
            },
        )

    return make_response(
        data={
            "file_id": record.id,
            "filename": record.filename,
            "file_size": record.file_size,
            "file_type": record.file_type,
            "parse_status": record.parse_status,
            "created_at": record.created_at.isoformat(),
        },
        message="上传成功",
    )


@router.get("")
async def list_files(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """文件列表（分页，按上传时间倒序）"""
    service = FileService(db)
    result = await service.get_user_files(
        user_id=str(current_user.id),
        page=page,
        page_size=page_size,
    )
    return make_paginated_response(
        items=result["items"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{file_id}/status")
async def get_file_status(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """查询文件解析状态"""
    service = FileService(db)
    result = await service.get_file_status(
        file_id=file_id,
        user_id=str(current_user.id),
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "文件不存在或无权访问",
            },
        )

    return make_response(data=result)


@router.post("/{file_id}/reparse")
async def reparse_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """重新解析文件"""
    service = FileService(db)
    record = await service.reparse_file(
        file_id=file_id,
        user_id=str(current_user.id),
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "文件不存在或无权访问",
            },
        )

    return make_response(
        data={
            "file_id": record.id,
            "filename": record.filename,
            "parse_status": record.parse_status,
        },
        message="重新解析已触发",
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除文件（数据库记录 + 磁盘文件）"""
    service = FileService(db)
    deleted = await service.delete_file(
        file_id=file_id,
        user_id=str(current_user.id),
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "文件不存在或无权访问",
            },
        )

    return make_response(message="文件已删除")
