"""
知识图谱路由 (PBI_11) — 生成、查询、导出
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_paginated_response, make_response
from app.schemas.knowledge import (
    GenerateGraphReq,
    KnowledgeGraphItem,
    KnowledgeGraphResp,
    NodeDetailResp,
    RelatedNode,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


@router.post("/graph", summary="生成知识图谱")
async def generate_graph(
    req: GenerateGraphReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """根据学科/章节生成知识图谱"""
    service = KnowledgeService(db)
    graph = await service.generate(
        user_id=current_user.id,
        source_type=req.source_type,
        source=req.source,
        file_id=req.file_id,
    )
    await db.commit()
    await db.refresh(graph)  # commit 后刷新，避免 MissingGreenlet
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
        page=page,
        page_size=page_size,
    )


@router.get("/graphs/{graph_id}", summary="查看图谱详情")
async def get_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
async def get_node_detail(
    graph_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
async def delete_graph(
    graph_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
