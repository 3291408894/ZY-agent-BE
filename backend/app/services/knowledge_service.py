"""知识图谱服务层 (PBI_11) — 图谱生成、查询、节点详情、导出"""

import json
import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.knowledge import (
    FILE_GRAPH_TEMPLATE,
    NODE_DETAIL_TEMPLATE,
    SUBJECT_GRAPH_TEMPLATE,
    SYSTEM_PROMPT,
)
from app.core.utils import extract_json
from app.models.file import UploadedFile
from app.models.knowledge import KnowledgeGraph
from app.schemas.knowledge import (
    CommonMistake,
    ExampleQuestion,
    GenerateGraphReq,
    GraphEdge,
    GraphNode,
    KnowledgeGraphItem,
    KnowledgeGraphListResponse,
    KnowledgeGraphResp,
    NodeDetailResponse,
)


class KnowledgeService:
    """知识图谱业务逻辑"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ═══════════════════════════════════════════════════════
    # 核心：生成知识图谱
    # ═══════════════════════════════════════════════════════

    async def generate_graph(
        self,
        user_id: str,
        req: GenerateGraphReq,
    ) -> KnowledgeGraphResp:
        """
        调用 LLM 生成知识图谱的节点和边，持久化并返回。
        """
        # 1. 构建 Prompt
        if req.source_type == "file" and req.file_id:
            # 从文件内容生成
            file_content = await self._get_file_content(req.file_id, user_id)
            user_prompt = FILE_GRAPH_TEMPLATE.format(content=file_content)
        else:
            # 按学科/章节生成
            subject, source = self._parse_subject_source(req.source)
            user_prompt = SUBJECT_GRAPH_TEMPLATE.format(
                subject=subject,
                source=source,
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 2. 调用 LLM 生成图谱数据
        try:
            response = await llm_client.chat_with_retry(
                messages, retries=2
            )
        except Exception as e:
            logger.error(f"LLM 图谱生成失败 | user={user_id} | error={e}")
            raise RuntimeError(
                f"知识图谱生成失败，AI 服务调用异常: {str(e)}"
            ) from e

        # 3. 解析 LLM 返回的 JSON
        graph_data = self._parse_graph_json(response)
        if not graph_data:
            raise RuntimeError("知识图谱生成失败，无法解析 AI 返回的图谱数据")

        nodes_raw = graph_data.get("nodes", [])
        edges_raw = graph_data.get("edges", [])
        title = graph_data.get("title", f"{req.source} 知识图谱")

        nodes = [
            GraphNode(
                id=n.get("id", f"n{i}"),
                label=n.get("label", ""),
                type=n.get("type", "knowledge"),
                x=float(n.get("x", 0)),
                y=float(n.get("y", 0)),
            )
            for i, n in enumerate(nodes_raw)
        ]

        edges = [
            GraphEdge(
                source=e.get("source", ""),
                target=e.get("target", ""),
                relation=e.get("relation", ""),
            )
            for e in edges_raw
        ]

        # 4. 持久化到数据库
        graph = KnowledgeGraph(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            nodes=[n.model_dump() for n in nodes],
            edges=[e.model_dump() for e in edges],
            source_type=req.source_type,
            created_at=datetime.now(UTC),
        )
        self.db.add(graph)
        await self.db.flush()

        logger.info(
            f"知识图谱已生成 | graph_id={graph.id} | title={title} | "
            f"nodes={len(nodes)} | edges={len(edges)} | user={user_id}"
        )

        return KnowledgeGraphResp(
            graph_id=graph.id,
            title=title,
            nodes=nodes,
            edges=edges,
            source_type=req.source_type,
            created_at=graph.created_at,
        )

    # ═══════════════════════════════════════════════════════
    # 查询：图谱列表（分页）
    # ═══════════════════════════════════════════════════════

    async def list_graphs(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> KnowledgeGraphListResponse:
        """分页查询用户的图谱列表"""
        conditions = [KnowledgeGraph.user_id == user_id]

        # 总数
        count_stmt = select(func.count()).select_from(KnowledgeGraph).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        stmt = (
            select(KnowledgeGraph)
            .where(*conditions)
            .order_by(KnowledgeGraph.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [
            KnowledgeGraphItem(
                id=row.id,
                title=row.title,
                source_type=row.source_type,
                node_count=len(row.nodes) if row.nodes else 0,
                edge_count=len(row.edges) if row.edges else 0,
                created_at=row.created_at,
            )
            for row in rows
        ]

        total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1

        return KnowledgeGraphListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # ═══════════════════════════════════════════════════════
    # 查询：单个图谱详情
    # ═══════════════════════════════════════════════════════

    async def get_graph(
        self, user_id: str, graph_id: str
    ) -> KnowledgeGraphResp | None:
        """查看单个图谱的完整数据"""
        stmt = select(KnowledgeGraph).where(
            KnowledgeGraph.id == graph_id,
            KnowledgeGraph.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        return KnowledgeGraphResp(
            graph_id=row.id,
            title=row.title,
            nodes=[GraphNode(**n) for n in (row.nodes or [])],
            edges=[GraphEdge(**e) for e in (row.edges or [])],
            source_type=row.source_type,
            created_at=row.created_at,
        )

    # ═══════════════════════════════════════════════════════
    # 节点详情：LLM 深入分析单个知识点
    # ═══════════════════════════════════════════════════════

    async def get_node_detail(
        self,
        user_id: str,
        graph_id: str,
        node_id: str,
    ) -> NodeDetailResponse | None:
        """获取图谱中某个节点的详细信息（含 LLM 生成的例题和易错点）"""
        # 1. 先查图谱
        graph = await self._get_graph_or_none(graph_id, user_id)
        if not graph:
            return None

        # 2. 查找节点
        target_node = None
        for n in (graph.nodes or []):
            if n.get("id") == node_id:
                target_node = n
                break
        if not target_node:
            return None

        node_label = target_node.get("label", "")
        node_type = target_node.get("type", "")

        # 3. 构建上下文信息
        context_parts = [graph.title]
        # 查找与该节点相关的边，获取关系语境
        related_info = []
        for e in (graph.edges or []):
            if e.get("source") == node_id:
                target_label = self._find_node_label(graph.nodes, e.get("target", ""))
                related_info.append(f"{e.get('relation', '关联')} → {target_label}")
            elif e.get("target") == node_id:
                source_label = self._find_node_label(graph.nodes, e.get("source", ""))
                related_info.append(f"{source_label} → {e.get('relation', '关联')}")
        if related_info:
            context_parts.append("图谱关系：" + "；".join(related_info))

        context = " | ".join(context_parts)

        # 4. 调用 LLM 获取节点详情
        if node_type == "knowledge":
            detail = await self._enrich_knowledge_node(node_label, context)
        else:
            detail = self._default_node_detail(node_label, node_type, context)

        return NodeDetailResponse(
            node_id=node_id,
            label=node_label,
            node_type=node_type,
            graph_id=graph_id,
            graph_title=graph.title,
            summary=detail.get("summary", ""),
            key_points=detail.get("key_points", []),
            example_questions=[
                ExampleQuestion(**q) for q in detail.get("example_questions", [])
            ],
            common_mistakes=[
                CommonMistake(**m) for m in detail.get("common_mistakes", [])
            ],
            related_knowledge=detail.get("related_knowledge", []),
        )

    # ═══════════════════════════════════════════════════════
    # 删除图谱
    # ═══════════════════════════════════════════════════════

    async def delete_graph(self, user_id: str, graph_id: str) -> bool:
        """删除一条图谱记录"""
        stmt = delete(KnowledgeGraph).where(
            KnowledgeGraph.id == graph_id,
            KnowledgeGraph.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"知识图谱已删除 | graph_id={graph_id} | user={user_id}")
        return deleted

    # ═══════════════════════════════════════════════════════
    # 导出图谱为 HTML（前端可渲染或截图）
    # ═══════════════════════════════════════════════════════

    async def export_graph_html(
        self,
        user_id: str,
        graph_id: str,
        width: int = 1200,
        height: int = 900,
        background: str = "#ffffff",
        include_title: bool = True,
    ) -> str | None:
        """导出图谱为可用于渲染/截图的 HTML 页面"""
        graph = await self._get_graph_or_none(graph_id, user_id)
        if not graph:
            return None

        return self._build_export_html(
            title=graph.title if include_title else "",
            nodes=graph.nodes or [],
            edges=graph.edges or [],
            width=width,
            height=height,
            background=background,
        )

    # ═══════════════════════════════════════════════════════
    # 私有辅助方法
    # ═══════════════════════════════════════════════════════

    async def _get_graph_or_none(
        self, graph_id: str, user_id: str
    ) -> KnowledgeGraph | None:
        """按 ID 和用户 ID 查询图谱"""
        stmt = select(KnowledgeGraph).where(
            KnowledgeGraph.id == graph_id,
            KnowledgeGraph.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _get_file_content(self, file_id: str, user_id: str) -> str:
        """读取已解析的文件内容"""
        stmt = select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == user_id,
        )
        file_row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not file_row:
            raise ValueError("文件不存在或无权访问")
        if file_row.parse_status != "done":
            raise ValueError("文件尚未解析完成，请等待解析完毕后再生成图谱")
        content = file_row.parsed_content or ""
        # 如果内容过长，截取前 8000 字
        if len(content) > 8000:
            content = content[:8000] + "\n...(内容已截断)"
        return content

    @staticmethod
    def _parse_subject_source(source: str) -> tuple[str, str]:
        """解析 '语文-七年级-文言文' 格式的 source -> (subject, source)"""
        parts = source.split("-", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return source.strip(), source.strip()

    @staticmethod
    def _parse_graph_json(response: str) -> dict | None:
        """从 LLM 回复中提取图谱 JSON"""
        json_str = extract_json(response)
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"图谱 JSON 解析失败，原始回复前200字: {response[:200]}")
            return None

    @staticmethod
    def _find_node_label(nodes: list[dict] | None, node_id: str) -> str:
        """在节点列表中按 ID 查找 label"""
        if not nodes:
            return node_id
        for n in nodes:
            if n.get("id") == node_id:
                return n.get("label", node_id)
        return node_id

    async def _enrich_knowledge_node(
        self, node_label: str, context: str
    ) -> dict:
        """调用 LLM 获取知识节点的详细分析"""
        try:
            prompt = NODE_DETAIL_TEMPLATE.format(
                node_label=node_label,
                context=context,
            )
            messages = [
                {"role": "system", "content": "你是一位K12教育专家。请严格按JSON格式输出。"},
                {"role": "user", "content": prompt},
            ]
            response = await llm_client.chat(
                messages, temperature=0.4, max_tokens=2048
            )
            json_match = extract_json(response)
            if json_match:
                return json.loads(json_match)
        except Exception as e:
            logger.warning(f"节点详情 LLM 调用失败 | node={node_label} | error={e}")

        return self._default_node_detail(node_label, "knowledge", context)

    @staticmethod
    def _default_node_detail(
        node_label: str, node_type: str, context: str
    ) -> dict:
        """LLM 不可用时的默认节点详情"""
        type_desc = {
            "category": f"'{node_label}' 是一个知识分类/模块节点",
            "article": f"'{node_label}' 是一篇课文/章节",
            "knowledge": f"'{node_label}' 是一个知识点",
        }
        return {
            "summary": type_desc.get(node_type, f"关于 '{node_label}' 的知识点"),
            "key_points": [f"掌握 {node_label} 的基本概念", f"理解 {node_label} 的核心要点"],
            "example_questions": [],
            "common_mistakes": [],
            "related_knowledge": [],
        }

    @staticmethod
    def _build_export_html(
        title: str,
        nodes: list[dict],
        edges: list[dict],
        width: int,
        height: int,
        background: str,
    ) -> str:
        """构建图谱导出的独立 HTML 页面（使用 Canvas 简单渲染）"""
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        edges_json = json.dumps(edges, ensure_ascii=False)
        title_style = (
            "text-align:center;font-family:sans-serif;"
            "color:#333;margin:0 0 16px 0;"
        )
        title_html = (
            f"<h1 style='{title_style}'>{title}</h1>" if title else ""
        )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title or '知识图谱'}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: {background};
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
}}
canvas {{ border-radius: 8px; }}
</style>
</head>
<body>
{title_html}
<canvas id="graphCanvas" width="{width}" height="{height}"></canvas>
<script>
(function() {{
  var nodes = {nodes_json};
  var edges = {edges_json};
  var canvas = document.getElementById('graphCanvas');
  var ctx = canvas.getContext('2d');
  var W = {width}, H = {height};

  // 颜色映射
  var colors = {{
    category: {{ bg: '#e8f0fe', border: '#5b9bd5', text: '#1a3a5c' }},
    article: {{ bg: '#fff3e0', border: '#e6a23c', text: '#5c3a1a' }},
    knowledge: {{ bg: '#e8f5e9', border: '#67c23a', text: '#1a3c1a' }}
  }};
  var defaultColor = {{ bg: '#f5f5f5', border: '#999', text: '#333' }};

  // 画边
  edges.forEach(function(e) {{
    var src = null, tgt = null;
    nodes.forEach(function(n) {{
      if (n.id === e.source) src = n;
      if (n.id === e.target) tgt = n;
    }});
    if (!src || !tgt) return;
    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.lineTo(tgt.x, tgt.y);
    ctx.strokeStyle = '#cccccc';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 边标签
    var mx = (src.x + tgt.x) / 2, my = (src.y + tgt.y) / 2;
    ctx.fillStyle = '#999';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(e.relation || '', mx, my - 6);
  }});

  // 画节点
  nodes.forEach(function(n) {{
    var c = colors[n.type] || defaultColor;
    var label = n.label || n.id;
    var fontSize = n.type === 'category' ? 15 : (n.type === 'article' ? 13 : 11);
    ctx.font = 'bold ' + fontSize + 'px sans-serif';
    var metrics = ctx.measureText(label);
    var tw = metrics.width;
    var th = fontSize;
    var padX = 12, padY = 8;
    var rw = tw + padX * 2, rh = th + padY * 2;
    var rx = n.x - rw / 2, ry = n.y - rh / 2;

    // 圆角矩形
    var radius = 6;
    ctx.beginPath();
    ctx.moveTo(rx + radius, ry);
    ctx.lineTo(rx + rw - radius, ry);
    ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + radius);
    ctx.lineTo(rx + rw, ry + rh - radius);
    ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - radius, ry + rh);
    ctx.lineTo(rx + radius, ry + rh);
    ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - radius);
    ctx.lineTo(rx, ry + radius);
    ctx.quadraticCurveTo(rx, ry, rx + radius, ry);
    ctx.closePath();
    ctx.fillStyle = c.bg;
    ctx.fill();
    ctx.strokeStyle = c.border;
    ctx.lineWidth = 2;
    ctx.stroke();

    // 文字
    ctx.fillStyle = c.text;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, n.x, n.y);
  }});
}})();
</script>
</body>
</html>"""
