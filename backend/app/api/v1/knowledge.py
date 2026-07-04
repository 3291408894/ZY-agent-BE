<<<<<<< HEAD
"""
知识图谱路由 (PBI_11) — 生成、查询、导出
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
=======
"""知识图谱模块 — API 路由 (PBI_11)

提供知识图谱的生成、查询、节点详情、删除和导出功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from loguru import logger
>>>>>>> main
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
<<<<<<< HEAD
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.knowledge import (
    GenerateGraphReq,
    KnowledgeGraphItem,
    KnowledgeGraphResp,
    NodeDetailResp,
    RelatedNode,
=======
from app.schemas.common import ErrorCode
from app.schemas.knowledge import (
    ExportRequest,
    GenerateGraphReq,
    KnowledgeGraphListResponse,
    KnowledgeGraphResp,
    NodeDetailResponse,
>>>>>>> main
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


<<<<<<< HEAD
@router.post("/graph", summary="生成知识图谱")
=======
# ═══════════════════════════════════════════════════════════
# POST /knowledge/graph — 生成知识图谱
# ═══════════════════════════════════════════════════════════

@router.post("/graph", response_model=KnowledgeGraphResp)
>>>>>>> main
async def generate_graph(
    req: GenerateGraphReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """根据学科/章节生成知识图谱"""
    service = KnowledgeService(db)
    graph = await service.generate(
        user_id=current_user.id,
        source_type=req.source_type,
        source=req.source,
        file_id=req.file_id,
    )
    await db.commit()
    return make_response(
        data=KnowledgeGraphResp(
            graph_id=graph.id,
            title=graph.title,
            nodes=graph.nodes or [],
            edges=graph.edges or [],
        ).model_dump(),
        message="图谱生成成功",
    )


@router.get("/graphs", summary="图谱列表")
async def list_graphs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有知识图谱（分页，含 node_count / edge_count）"""
    service = KnowledgeService(db)
    graphs, total = await service.list_graphs(current_user.id, page, page_size)
    return make_paginated_response(
        items=[
            KnowledgeGraphItem(
                id=g.id,
                title=g.title,
                node_count=len(g.nodes or []),
                edge_count=len(g.edges or []),
                source_type=g.source_type,
                created_at=g.created_at,
            ).model_dump()
            for g in graphs
        ],
        total=total,
=======
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
>>>>>>> main
        page=page,
        page_size=page_size,
    )


<<<<<<< HEAD
@router.get("/graphs/{graph_id}", summary="查看图谱详情")
=======
# ═══════════════════════════════════════════════════════════
# GET /knowledge/graphs/{graph_id} — 查看图谱详情
# ═══════════════════════════════════════════════════════════

@router.get("/graphs/{graph_id}", response_model=KnowledgeGraphResp)
>>>>>>> main
async def get_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """查看指定图谱的完整数据（节点 + 边）"""
    service = KnowledgeService(db)
    graph = await service.get_graph(graph_id, current_user.id)
    if not graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "图谱不存在", "detail": None},
        )
    return make_response(
        data=KnowledgeGraphResp(
            graph_id=graph.id,
            title=graph.title,
            nodes=graph.nodes or [],
            edges=graph.edges or [],
        ).model_dump()
    )


@router.get("/graphs/{graph_id}/node/{node_id}", summary="节点详情")
=======
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
>>>>>>> main
async def get_node_detail(
    graph_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """查看图谱中某个节点的详细信息及关联节点"""
    service = KnowledgeService(db)
    detail = await service.get_node_detail(graph_id, node_id, current_user.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "图谱或节点不存在", "detail": None},
        )
    return make_response(data=detail)


@router.delete("/graphs/{graph_id}", summary="删除图谱")
=======
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
>>>>>>> main
async def delete_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """删除指定知识图谱"""
    service = KnowledgeService(db)
    success = await service.delete_graph(graph_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "图谱不存在", "detail": None},
        )
    await db.commit()
    return make_response(message="删除成功")


@router.post("/graphs/{graph_id}/export", summary="导出图片数据")
async def export_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出图谱数据（前端接收后渲染为图片）"""
    service = KnowledgeService(db)
    data = await service.export_graph(graph_id, current_user.id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.RESOURCE_NOT_FOUND, "message": "图谱不存在", "detail": None},
        )
    return make_response(data=data, message="导出数据已生成")
=======
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
>>>>>>> main
