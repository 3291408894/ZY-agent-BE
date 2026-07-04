"""
知识图谱服务层 (PBI_11)
"""

import json
import uuid
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.models.knowledge import KnowledgeGraph

KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """你是一位资深的教育专家，擅长构建学科知识图谱。

## 任务
根据指定的学科/章节，生成一个结构化的知识图谱，包含节点和边。

## 节点类型
- category: 学科分类节点
- chapter: 章节节点
- knowledge: 知识点节点（叶子节点）

## 输出格式
请严格输出以下 JSON 格式：
{
  "title": "图谱标题",
  "nodes": [
    {"id": "1", "label": "节点名称", "type": "category", "x": 0, "y": 0}
  ],
  "edges": [
    {"source": "1", "target": "2", "relation": "包含"}
  ]
}

要求：
1. 节点数量 5-30 个
2. 至少包含 3 层结构（学科 → 章节 → 知识点）
3. 每个节点有合理的坐标位置 (x, y)，范围 0-800
4. 边的关系用中文描述（包含/属于/关联/前置等）
5. 层级清晰，结构合理"""

KNOWLEDGE_GRAPH_USER_TEMPLATE = """请为以下内容生成知识图谱：

学科/章节：{source}
类型：{source_type}"""


class KnowledgeService:
    """知识图谱业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(
        self,
        user_id: str,
        source_type: str,
        source: str,
        file_id: str | None = None,
    ) -> KnowledgeGraph:
        """生成知识图谱"""
        messages = [
            {"role": "system", "content": KNOWLEDGE_GRAPH_SYSTEM_PROMPT},
            {"role": "user", "content": KNOWLEDGE_GRAPH_USER_TEMPLATE.format(
                source=source, source_type=source_type
            )},
        ]

        try:
            response = await llm_client.chat_with_retry(messages)
            data = self._parse_graph_json(response)
        except Exception as e:
            logger.error(f"图谱生成失败: {e}")
            # 降级：返回一个基础骨架
            data = {
                "title": f"{source} 知识图谱",
                "nodes": [
                    {"id": "1", "label": source, "type": "category", "x": 400, "y": 50},
                    {"id": "2", "label": "基础知识", "type": "chapter", "x": 200, "y": 300},
                    {"id": "3", "label": "进阶内容", "type": "chapter", "x": 600, "y": 300},
                ],
                "edges": [
                    {"source": "1", "target": "2", "relation": "包含"},
                    {"source": "1", "target": "3", "relation": "包含"},
                ],
            }

        # 确保每个节点有唯一 ID
        for i, node in enumerate(data.get("nodes", [])):
            if "id" not in node:
                node["id"] = str(i + 1)
            if "x" not in node:
                node["x"] = (i % 3) * 250 + 100
            if "y" not in node:
                node["y"] = (i // 3) * 150 + 80

        graph = KnowledgeGraph(
            user_id=user_id,
            title=data.get("title", f"{source} 知识图谱"),
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            source_type=source_type,
        )
        self.db.add(graph)
        await self.db.flush()
        return graph

    async def list_graphs(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[KnowledgeGraph], int]:
        """获取用户的图谱列表（按时间倒序，含 node_count/edge_count）"""
        count_stmt = (
            select(func.count())
            .select_from(KnowledgeGraph)
            .where(KnowledgeGraph.user_id == user_id)
        )
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        stmt = (
            select(KnowledgeGraph)
            .where(KnowledgeGraph.user_id == user_id)
            .order_by(KnowledgeGraph.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        graphs = list(result.scalars().all())
        return graphs, total

    async def get_graph(self, graph_id: str, user_id: str) -> KnowledgeGraph | None:
        """获取单个图谱"""
        graph = await self.db.get(KnowledgeGraph, graph_id)
        if graph and graph.user_id == user_id:
            return graph
        return None

    async def get_node_detail(
        self, graph_id: str, node_id: str, user_id: str
    ) -> dict | None:
        """获取图谱中某个节点的详情（对齐 spec: node_id, label, description, examples, common_mistakes, related_nodes）"""
        graph = await self.get_graph(graph_id, user_id)
        if not graph:
            return None
        nodes = graph.nodes or []
        edges = graph.edges or []

        target_node = None
        for node in nodes:
            if node.get("id") == node_id:
                target_node = node
                break

        if not target_node:
            return None

        # 找关联节点
        related_nodes = []
        for e in edges:
            if e.get("source") == node_id:
                neighbor_id = e.get("target")
                neighbor = next((n for n in nodes if n.get("id") == neighbor_id), None)
                if neighbor:
                    related_nodes.append({
                        "id": neighbor.get("id", ""),
                        "label": neighbor.get("label", ""),
                        "relation": e.get("relation", ""),
                    })
            elif e.get("target") == node_id:
                neighbor_id = e.get("source")
                neighbor = next((n for n in nodes if n.get("id") == neighbor_id), None)
                if neighbor:
                    related_nodes.append({
                        "id": neighbor.get("id", ""),
                        "label": neighbor.get("label", ""),
                        "relation": e.get("relation", ""),
                    })

        return {
            "node_id": target_node.get("id", node_id),
            "label": target_node.get("label", ""),
            "description": target_node.get("description", ""),
            "examples": target_node.get("examples", []),
            "common_mistakes": target_node.get("common_mistakes", []),
            "related_nodes": related_nodes,
        }

    async def delete_graph(self, graph_id: str, user_id: str) -> bool:
        """删除图谱"""
        graph = await self.db.get(KnowledgeGraph, graph_id)
        if not graph or graph.user_id != user_id:
            return False
        await self.db.delete(graph)
        await self.db.flush()
        return True

    async def export_graph(self, graph_id: str, user_id: str) -> dict | None:
        """导出图谱数据（前端用此数据渲染为图片）"""
        graph = await self.get_graph(graph_id, user_id)
        if not graph:
            return None
        return {
            "title": graph.title,
            "nodes": graph.nodes,
            "edges": graph.edges,
            "source_type": graph.source_type,
            "created_at": graph.created_at.isoformat() if graph.created_at else "",
        }

    @staticmethod
    def _parse_graph_json(text: str) -> dict:
        """从 LLM 返回文本中提取图谱 JSON"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"无法解析 LLM 返回的图谱 JSON: {text[:200]}")
            return {"title": "知识图谱", "nodes": [], "edges": []}
