"""
班级资源路由 — 学生端：查看班级共享资源 + 保存到知识库 + 查看/下载班级试卷
"""

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.services.class_resource_service import ClassResourceService
from app.services.class_exam_paper_service import ClassExamPaperService

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


# ============================================================
# 班级试卷列表
# ============================================================

@router.get("/classes/{class_id}/exam-papers", summary="班级试卷列表")
async def list_class_exam_papers(
    class_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生查看班级已分享的试卷列表（需已加入该班级）"""
    service = ClassExamPaperService(db)
    try:
        await service._verify_student_in_class(class_id, current_user.id)
        items, total = await service.list_class_exam_papers(
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
# 下载班级试卷
# ============================================================

@router.get("/classes/{class_id}/exam-papers/{paper_id}/download", summary="下载班级试卷")
async def download_class_exam_paper(
    class_id: str,
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学生下载班级共享的试卷文件"""
    service = ClassExamPaperService(db)

    # 验证学生属于该班级
    try:
        await service._verify_student_in_class(class_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": str(e), "detail": None},
        )

    # 查询试卷
    from app.models.exam_paper import ExamPaper
    from app.models.class_exam_paper import ClassExamPaper
    from sqlalchemy import select, and_

    share = await db.scalar(
        select(ClassExamPaper).where(
            and_(
                ClassExamPaper.class_id == class_id,
                ClassExamPaper.exam_paper_id == paper_id,
            )
        )
    )
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "试卷未分享到此班级", "detail": None},
        )

    paper = await db.scalar(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "试卷不存在", "detail": None},
        )

    # 检查是否有导出文件
    if not paper.export_url or not os.path.isfile(paper.export_url):
        # 如果没有导出文件，则实时导出
        from app.services.exam_paper_service import ExamPaperService
        from app.schemas.exam_paper import ExportFormat

        paper_service = ExamPaperService(db)
        result = await paper_service.export_paper(
            user_id=paper.user_id,
            paper_id=paper_id,
            export_format=ExportFormat.WORD,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": ErrorCode.INTERNAL_ERROR, "message": "试卷导出失败", "detail": None},
            )
        await db.commit()
        file_path, file_name = result
    else:
        file_path = paper.export_url
        file_name = f"{paper.title}.docx"

    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    encoded_filename = quote(file_name)

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
