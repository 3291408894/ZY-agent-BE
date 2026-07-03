"""课文总结模块 — 业务逻辑层 (PBI_06)"""

import json
import uuid
from typing import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from loguru import logger

from app.models.summary import Summary
from app.schemas.summary import (
    SummaryMode,
    SummarySourceType,
    SummaryItem,
    SummaryDetailResponse,
    SummaryListResponse,
    KnowledgePoint,
)
from app.ai.llm_client import llm_client
from app.ai.prompts.summary import (
    SYSTEM_PROMPT,
    BRIEF_SUMMARY_TEMPLATE,
    DETAILED_SUMMARY_TEMPLATE,
    KNOWLEDGE_POINTS_EXTRACTION_TEMPLATE,
)
from app.core.utils import sse_json, truncate, extract_json


class SummaryService:
    """课文总结服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─────────────────────────────────────────────────────
    # 核心：流式生成总结
    # ─────────────────────────────────────────────────────

    async def generate_summary_stream(
        self,
        user_id: str,
        content: str,
        mode: SummaryMode,
    ) -> AsyncIterator[str]:
        """
        SSE 流式生成课文总结。
        每个 yield 返回一行 SSE 格式的 JSON 字符串（不含 'data: ' 前缀）。
        """
        # 1. 选择 Prompt 模板
        template = (
            DETAILED_SUMMARY_TEMPLATE
            if mode == SummaryMode.DETAILED
            else BRIEF_SUMMARY_TEMPLATE
        )
        user_prompt = template.format(content=content)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 2. 流式调用 LLM
        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(messages, temperature=0.5):
                full_text += chunk
                yield sse_json({"type": "content", "chunk": chunk})
        except Exception as e:
            logger.error(f"LLM 流式调用失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"AI 服务调用失败: {str(e)}"})
            return

        # 3. 提取知识点
        knowledge_points = await self._extract_knowledge_points(full_text)
        yield sse_json({
            "type": "knowledge_points",
            "points": [kp.model_dump() for kp in knowledge_points],
        })

        # 4. 持久化到数据库
        summary = Summary(
            id=str(uuid.uuid4()),
            user_id=user_id,
            source_type=SummarySourceType.TEXT.value,
            source_content=content,
            summary_text=full_text,
            mode=mode.value,
            knowledge_points=[kp.model_dump() for kp in knowledge_points],
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(summary)
        await self.db.flush()  # flush 产生 ID，由 deps.get_db 统一 commit

        logger.info(f"总结已保存 | summary_id={summary.id} | user={user_id} | mode={mode.value} | len={len(full_text)}")

        # 5. 完成事件
        yield sse_json({
            "type": "done",
            "summary_id": summary.id,
            "mode": mode.value,
        })

    # ─────────────────────────────────────────────────────
    # 知识点提取
    # ─────────────────────────────────────────────────────

    async def _extract_knowledge_points(self, summary_text: str) -> list[KnowledgePoint]:
        """从总结文本中提取知识点"""
        try:
            prompt = KNOWLEDGE_POINTS_EXTRACTION_TEMPLATE.format(summary_text=summary_text)
            messages = [
                {"role": "system", "content": "你是一位K12教育专家。请严格按JSON格式输出。"},
                {"role": "user", "content": prompt},
            ]
            response = await llm_client.chat_complete(
                messages, temperature=0.3, max_tokens=2048
            )
            # 尝试从回复中提取 JSON
            json_match = extract_json(response)
            if json_match:
                data = json.loads(json_match)
                return [
                    KnowledgePoint(name=item["name"], category=item.get("category", ""))
                    for item in data
                ]
        except Exception as e:
            logger.warning(f"知识点提取失败，将返回空列表: {e}")

        return []

    # ─────────────────────────────────────────────────────
    # 查询：历史列表
    # ─────────────────────────────────────────────────────

    async def list_summaries(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        mode: SummaryMode | None = None,
    ) -> SummaryListResponse:
        """分页查询历史总结记录"""
        # 构建查询
        conditions = [Summary.user_id == user_id]
        if mode:
            conditions.append(Summary.mode == mode.value)

        # 总数
        count_stmt = select(func.count()).select_from(Summary).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        stmt = (
            select(Summary)
            .where(*conditions)
            .order_by(Summary.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [
            SummaryItem(
                id=row.id,
                source_type=SummarySourceType(row.source_type),
                source_content=truncate(row.source_content, 200),
                summary_text=truncate(row.summary_text, 300),
                mode=SummaryMode(row.mode),
                knowledge_points=[
                    KnowledgePoint(**kp) for kp in (row.knowledge_points or [])
                ],
                created_at=row.created_at,
            )
            for row in rows
        ]

        total_pages = max(1, (total + page_size - 1) // page_size)

        return SummaryListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # ─────────────────────────────────────────────────────
    # 查询：单条详情
    # ─────────────────────────────────────────────────────

    async def get_summary(self, user_id: str, summary_id: str) -> SummaryDetailResponse | None:
        """查看单条总结详情"""
        stmt = select(Summary).where(
            Summary.id == summary_id,
            Summary.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        return SummaryDetailResponse(
            id=row.id,
            source_type=SummarySourceType(row.source_type),
            source_content=row.source_content,
            summary_text=row.summary_text,
            mode=SummaryMode(row.mode),
            knowledge_points=[
                KnowledgePoint(**kp) for kp in (row.knowledge_points or [])
            ],
            created_at=row.created_at,
        )

    # ─────────────────────────────────────────────────────
    # 删除
    # ─────────────────────────────────────────────────────

    async def delete_summary(self, user_id: str, summary_id: str) -> bool:
        """删除一条总结记录（软性校验归属）"""
        stmt = delete(Summary).where(
            Summary.id == summary_id,
            Summary.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"总结已删除 | summary_id={summary_id} | user={user_id}")
        return deleted
