"""
文件管理路由 (PBI_05) — 上传、解析、状态查询
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.common import ErrorCode, make_response
from app.schemas.file import FileItem, FileStatusResp, FileUploadResp
from app.services.file_service import FileService

router = APIRouter()


@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile,
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
            },
        )

    service = FileService(db)
    try:
        record = await service.upload(current_user.id, file.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.FILE_FORMAT_UNSUPPORTED, "message": str(e)},
        )

    await db.commit()

    # 异步触发解析（简化版：同步解析；生产环境用 Celery）
    try:
        await service.parse_file(record.id)
        await db.commit()
    except Exception:
        pass  # 解析失败不影响上传成功

    return make_response(
        data=FileUploadResp(
            file_id=record.id,
            filename=record.filename,
            file_size=record.file_size,
            file_type=record.file_type,
            parse_status=record.parse_status,
            created_at=record.created_at,
        ).model_dump(),
        message="上传成功",
    )


@router.get("", summary="文件列表")
async def list_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户上传的所有文件"""
    service = FileService(db)
    files = await service.list_files(current_user.id)
    return make_response(
        data=[
            FileItem(
                id=f.id,
                filename=f.filename,
                file_type=f.file_type,
                file_size=f.file_size,
                parse_status=f.parse_status,
                created_at=f.created_at,
            ).model_dump()
            for f in files
        ]
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
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在"},
        )
    return make_response(
        data=FileStatusResp(
            file_id=record.id,
            parse_status=record.parse_status,
            parsed_content=record.parsed_content,
        ).model_dump()
    )


@router.post("/{file_id}/reparse", summary="重新解析")
async def reparse_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新触发文件解析"""
    service = FileService(db)
    try:
        await service.reparse(file_id, current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在"},
        )
    await db.commit()
    return make_response(message="重新解析已触发")


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
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "文件不存在"},
        )
    await db.commit()
    return make_response(message="删除成功")
