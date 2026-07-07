"""
知识图谱服务层 (PBI_11)

负责:
- LLM 驱动的知识图谱生成
- 图谱 CRUD（列表、详情、节点查询、删除、导出）
"""

import json
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import desc, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.core.utils import extract_json
from app.models.knowledge import KnowledgeGraph

KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """你是一位 K12 教育专家，擅长梳理学科知识体系。

## 任务
根据给定的学科/章节/知识点，生成一个知识图谱，展示知识点之间的关联关系。

## 图谱结构
知识图谱由节点 (nodes) 和边 (edges) 组成：
- 节点：每个知识点作为一个节点
- 边：有关系的知识点之间用边连接

## 输出格式
请以 JSON 格式输出：
{
  "title": "图谱标题",
  "nodes": [
    {"id": "node_1", "label": "知识点名称", "type": "knowledge", "x": 0, "y": 0},
    ...
  ],
  "edges": [
    {"source": "node_1", "target": "node_2", "relation": "前置知识 / 关联知识 / 包含关系"},
    ...
  ]
}

对于 node 的 type 字段：
- "category": 大类节点（如"代数"、"几何"）
- "knowledge": 具体知识点节点
- "article": 课文/文章节点

坐标 x, y 用于前端可视化，你可以给出合理的初始布局（范围建议 0-800）。

请严格输出 JSON，不要包含其他文字。"""

KNOWLEDGE_GRAPH_USER_TEMPLATE = """请为以下内容生成知识图谱：

学科/章节：{source}
生成类型：{source_type}

请梳理出核心知识点及其关联关系，节点数量在 8-20 个之间。"""


class KnowledgeService:
    """知识图谱业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # 生成知识图谱
    # ================================================================

    async def generate(
        self,
        user_id: str,
        source_type: str,
        source: str,
        file_id: str | None = None,
    ) -> KnowledgeGraph:
        """
        使用 LLM 生成知识图谱。

        参数:
            user_id: 用户 ID
            source_type: subject / chapter / file
            source: 学科名或章节名
            file_id: 关联的文件 ID（可选）

        返回:
            持久化后的 KnowledgeGraph 对象
        """
        user_prompt = KNOWLEDGE_GRAPH_USER_TEMPLATE.format(
            source=source,
            source_type=source_type,
        )

        messages = [
            {"role": "system", "content": KNOWLEDGE_GRAPH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 调用 LLM 生成图谱
        try:
            response = await llm_client.chat(
                messages, temperature=0.5, max_tokens=4096
            )
            json_str = extract_json(response)
            if json_str:
                data = json.loads(json_str)
            else:
                data = json.loads(response.strip())

            # 如果 LLM 返回的是数组而非对象，包装为对象
            if isinstance(data, list):
                data = {
                    "title": source,
                    "nodes": data,
                    "edges": [],
                }
        except Exception as e:
            logger.error(f"LLM 知识图谱生成失败 | user={user_id} | error={e}")
            # 回退：生成空图谱
            data = {
                "title": source,
                "nodes": [],
                "edges": [],
            }

        title = data.get("title", source)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # 确保每个节点都有必要的字段
        for i, node in enumerate(nodes):
            if "id" not in node:
                node["id"] = f"node_{i}"
            if "x" not in node or "y" not in node:
                # 简单的圆形布局
                import math
                angle = (2 * math.pi * i) / max(len(nodes), 1)
                node["x"] = round(400 + 250 * math.cos(angle), 1)
                node["y"] = round(400 + 250 * math.sin(angle), 1)
            if "type" not in node:
                node["type"] = "knowledge"

        # 持久化
        graph = KnowledgeGraph(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
        )
        self.db.add(graph)
        await self.db.flush()

        logger.info(
            f"知识图谱已生成 | graph_id={graph.id} | user={user_id} "
            f"| nodes={len(nodes)} | edges={len(edges)}"
        )

        return graph

    # ================================================================
    # 图谱列表
    # ================================================================

    async def list_graphs(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeGraph], int]:
        """获取当前用户的知识图谱列表（分页，按创建时间倒序）"""
        count_stmt = (
            select(func.count())
            .select_from(KnowledgeGraph)
            .where(KnowledgeGraph.user_id == user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(KnowledgeGraph)
            .where(KnowledgeGraph.user_id == user_id)
            .order_by(desc(KnowledgeGraph.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        graphs = list(result.scalars().all())

        return graphs, total

    # ================================================================
    # 图谱详情
    # ================================================================

    async def get_graph(
        self, graph_id: str, user_id: str
    ) -> KnowledgeGraph | None:
        """查看指定图谱的完整数据"""
        graph = await self.db.get(KnowledgeGraph, graph_id)
        if graph and graph.user_id == user_id:
            return graph
        return None

    # ================================================================
    # 节点详情
    # ================================================================

    async def get_node_detail(
        self, graph_id: str, node_id: str, user_id: str
    ) -> dict | None:
        """
        查看图谱中某个节点的详细信息及关联节点。

        返回: {node: {...}, related_nodes: [...], related_edges: [...]}
        """
        graph = await self.get_graph(graph_id, user_id)
        if not graph:
            return None

        nodes = graph.nodes or []
        edges = graph.edges or []

        # 查找目标节点
        target_node = None
        for node in nodes:
            if node.get("id") == node_id:
                target_node = node
                break

        if not target_node:
            return None

        # 查找相关边和节点
        related_edges = []
        related_node_ids = set()
        for edge in edges:
            if edge.get("source") == node_id or edge.get("target") == node_id:
                related_edges.append(edge)
                related_node_ids.add(edge.get("source"))
                related_node_ids.add(edge.get("target"))

        related_node_ids.discard(node_id)
        related_nodes = [n for n in nodes if n.get("id") in related_node_ids]

        return {
            "node": target_node,
            "related_nodes": related_nodes,
            "related_edges": related_edges,
        }

    # ================================================================
    # 删除图谱
    # ================================================================

    async def delete_graph(self, graph_id: str, user_id: str) -> bool:
        """删除指定知识图谱"""
        graph = await self.db.get(KnowledgeGraph, graph_id)
        if not graph or graph.user_id != user_id:
            return False

        await self.db.delete(graph)
        await self.db.flush()
        logger.info(f"知识图谱已删除 | graph_id={graph_id} | user={user_id}")
        return True

    # ================================================================
    # 导出图谱数据
    # ================================================================

    async def export_graph(
        self, graph_id: str, user_id: str
    ) -> dict | None:
        """
        导出图谱数据（前端接收后渲染为图片）。

        返回: {graph_id, title, nodes, edges, export_time}
        """
        graph = await self.get_graph(graph_id, user_id)
        if not graph:
            return None

        from datetime import datetime, timezone

        return {
            "graph_id": graph.id,
            "title": graph.title,
            "nodes": graph.nodes or [],
            "edges": graph.edges or [],
            "export_time": datetime.now(timezone.utc).isoformat(),
        }
