"""试卷生成器 — API 路由 (功能2)"""

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_teacher, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.exam_paper import (
    ExamPaperGenerateRequest,
    ExamPaperExportRequest,
    ExamPaperListResponse,
    ExamPaperDetail,
    ExportFormat,
)
from app.services.exam_paper_service import ExamPaperService

router = APIRouter()


# ============================================================
# POST /generate — SSE 流式生成试卷
# ============================================================

@router.post("/generate", summary="AI生成试卷（SSE流式）")
async def generate_exam_paper(
    req: ExamPaperGenerateRequest,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    AI 流式生成试卷（SSE 事件流）。

    SSE 事件类型:
    - thinking:  思考阶段（stage: analyzing）
    - content:   试卷内容增量
    - progress:  进度状态（stage: parsing, answer_sheet）
    - done:      生成完成（含 paper_id）
    - error:     出错信息
    """
    service = ExamPaperService(db)

    async def event_stream():
        async for sse_line in service.generate_exam_paper_sse(
            user_id=current_user.id,
            req=req,
        ):
            yield f"data: {sse_line}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# GET / — 历史试卷列表
# ============================================================

@router.get("", summary="历史试卷列表")
async def list_exam_papers(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    subject: str | None = Query(default=None, description="学科筛选"),
    exam_type: str | None = Query(default=None, description="考试类型筛选"),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取历史试卷记录（分页）"""
    service = ExamPaperService(db)
    result = await service.list_exam_papers(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        subject=subject,
        exam_type=exam_type,
    )
    return make_paginated_response(
        items=[item.model_dump(mode="json") for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


# ============================================================
# GET /{paper_id} — 试卷详情
# ============================================================

@router.get("/{paper_id}", summary="试卷详情")
async def get_exam_paper_detail(
    paper_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """查看试卷详情（含完整试卷内容、答题卡）"""
    service = ExamPaperService(db)
    result = await service.get_detail(current_user.id, paper_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "试卷不存在或无权查看",
                "detail": None,
            },
        )
    return make_response(data=result.model_dump(mode="json"))


# ============================================================
# DELETE /{paper_id} — 删除试卷
# ============================================================

@router.delete("/{paper_id}", summary="删除试卷")
async def delete_exam_paper(
    paper_id: str,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """删除一条试卷记录"""
    service = ExamPaperService(db)
    deleted = await service.delete(current_user.id, paper_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "试卷不存在或无权操作",
                "detail": None,
            },
        )
    return make_response(message="删除成功")


# ============================================================
# POST /{paper_id}/export — 导出试卷
# ============================================================

@router.post("/{paper_id}/export", summary="导出试卷")
async def export_exam_paper(
    paper_id: str,
    req: ExamPaperExportRequest,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    导出试卷为 Word/PDF/Printable 格式。

    返回文件下载链接。
    """
    service = ExamPaperService(db)
    result = await service.export_paper(
        user_id=current_user.id,
        paper_id=paper_id,
        export_format=req.format,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "试卷不存在或无权操作",
                "detail": None,
            },
        )

    file_path, file_name = result
    await db.commit()

    # 构造 Media Type
    media_type_map = {
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(req.format.value, "application/octet-stream")

    encoded_filename = quote(file_name)

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
