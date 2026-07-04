"""知识图谱模块 — API 路由 (PBI_11)

提供知识图谱的生成、查询、节点详情、删除和导出功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode
from app.schemas.knowledge import (
    ExportRequest,
    GenerateGraphReq,
    KnowledgeGraphListResponse,
    KnowledgeGraphResp,
    NodeDetailResponse,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# POST /knowledge/graph — 生成知识图谱
# ═══════════════════════════════════════════════════════════

@router.post("/graph", response_model=KnowledgeGraphResp)
async def generate_graph(
    req: GenerateGraphReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成知识图谱。

    支持三种来源类型：
    - subject: 按学科范围生成（如"语文-七年级-文言文"）
    - chapter: 按教材章节生成
    - file:    基于已上传并解析完成的文件内容生成

    返回图谱的节点和边数据，可直接用于前端 ECharts 渲染。
    """
    # 参数校验
    if req.source_type == "file" and not req.file_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.PARAM_INVALID,
                "message": "source_type=file 时 file_id 不能为空",
                "detail": None,
            },
        )

    service = KnowledgeService(db)
    try:
        result = await service.generate_graph(
            user_id=current_user.id,
            req=req,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.PARAM_INVALID,
                "message": str(e),
                "detail": None,
            },
        ) from e
    except RuntimeError as e:
        logger.error(f"图谱生成失败 | user={current_user.id} | error={e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.LLM_SERVICE_ERROR,
                "message": str(e),
                "detail": None,
            },
        ) from e


# ═══════════════════════════════════════════════════════════
# GET /knowledge/graphs — 图谱列表（分页）
# ═══════════════════════════════════════════════════════════

@router.get("/graphs", response_model=KnowledgeGraphListResponse)
async def list_graphs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的知识图谱列表（分页，按创建时间倒序）"""
    service = KnowledgeService(db)
    return await service.list_graphs(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


# ═══════════════════════════════════════════════════════════
# GET /knowledge/graphs/{graph_id} — 查看图谱详情
# ═══════════════════════════════════════════════════════════

@router.get("/graphs/{graph_id}", response_model=KnowledgeGraphResp)
async def get_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看单个知识图谱的完整数据（含所有节点和边）"""
    service = KnowledgeService(db)
    result = await service.get_graph(current_user.id, graph_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "知识图谱不存在或无权访问",
                "detail": None,
            },
        )
    return result


# ═══════════════════════════════════════════════════════════
# GET /knowledge/graphs/{graph_id}/node/{node_id} — 节点详情
# ═══════════════════════════════════════════════════════════

@router.get(
    "/graphs/{graph_id}/node/{node_id}",
    response_model=NodeDetailResponse,
)
async def get_node_detail(
    graph_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    查看图谱中某个节点的详细信息。

    对于 knowledge 类型节点，会调用 LLM 生成：
    - 知识点概述
    - 核心要点列表
    - 典型例题（含答案）
    - 常见易错点及纠正建议
    - 关联知识点
    """
    service = KnowledgeService(db)
    result = await service.get_node_detail(
        user_id=current_user.id,
        graph_id=graph_id,
        node_id=node_id,
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "图谱或节点不存在",
                "detail": None,
            },
        )
    return result


# ═══════════════════════════════════════════════════════════
# DELETE /knowledge/graphs/{graph_id} — 删除图谱
# ═══════════════════════════════════════════════════════════

@router.delete("/graphs/{graph_id}")
async def delete_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条知识图谱记录"""
    service = KnowledgeService(db)
    deleted = await service.delete_graph(current_user.id, graph_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "知识图谱不存在或无权操作",
                "detail": None,
            },
        )
    return {"code": 0, "message": "删除成功", "data": None}


# ═══════════════════════════════════════════════════════════
# POST /knowledge/graphs/{graph_id}/export — 导出图谱
# ═══════════════════════════════════════════════════════════

@router.post("/graphs/{graph_id}/export")
async def export_graph(
    graph_id: str,
    req: ExportRequest = ExportRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出知识图谱。

    返回一个独立的 HTML 页面，可直接在浏览器中打开，
    也可通过前端截图工具（如 html2canvas）转为 PNG/SVG/PDF。

    支持的格式：
    - png/svg/pdf：返回 HTML 页面（由前端渲染后截图/打印）
    """
    service = KnowledgeService(db)
    html = await service.export_graph_html(
        user_id=current_user.id,
        graph_id=graph_id,
        width=req.width,
        height=req.height,
        background=req.background,
        include_title=req.include_title,
    )

    if not html:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND,
                "message": "知识图谱不存在或无权操作",
                "detail": None,
            },
        )

    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            "Content-Disposition": f"inline; filename=knowledge_graph_{graph_id}.html",
            "X-Graph-Format": req.format.value,
        },
    )
