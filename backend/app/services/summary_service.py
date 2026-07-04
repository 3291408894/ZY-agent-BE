"""课文总结模块 — 业务逻辑层 (PBI_06)"""

import json
import uuid
from typing import AsyncIterator
from datetime import datetime, timezone

import json
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import func, select
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

from app.ai.llm_client import llm_client
from app.ai.prompts.summary import (
    BRIEF_PROMPT_TEMPLATE,
    DETAILED_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
)
from app.models.summary import Summary


class SummaryService:
    """课文总结服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

<<<<<<< HEAD
    async def create_summary(
        self,
        user_id: str,
        source_type: str,
        content: str,
        mode: str = "detailed",
        file_id: str | None = None,
    ) -> Summary:
        """创建总结记录（初始为空）"""
        summary = Summary(
            user_id=user_id,
            source_type=source_type,
            source_content=content,
            mode=mode,
            summary_text="",
            knowledge_points=[],
        )
        self.db.add(summary)
        await self.db.flush()
        return summary

    async def update_summary_result(
        self, summary_id: str, summary_text: str, knowledge_points: list
    ) -> None:
        """更新总结结果"""
        summary = await self.db.get(Summary, summary_id)
        if summary:
            summary.summary_text = summary_text
            summary.knowledge_points = knowledge_points
            self.db.add(summary)
            await self.db.flush()

    async def generate_stream(
        self,
        user_id: str,
        source_type: str,
        content: str,
        mode: str = "detailed",
        file_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """流式生成总结 — 对齐 spec: content → knowledge_points → done"""
        # 创建记录
        summary = await self.create_summary(user_id, source_type, content, mode, file_id)

        # 选择 prompt 模板
        if mode == "brief":
            user_prompt = BRIEF_PROMPT_TEMPLATE.format(content=content)
        else:
            user_prompt = DETAILED_PROMPT_TEMPLATE.format(content=content)

        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(messages):
                full_text += chunk
                yield {"type": "content", "chunk": chunk}

            # 提取知识点（格式化为 KnowledgePoint 列表）
            raw_points = self._extract_knowledge_points(full_text)
            knowledge_points = [
                {"name": p, "category": "知识点"} for p in raw_points
            ]

            # 发送知识点事件
            yield {"type": "knowledge_points", "points": knowledge_points}

            # 更新记录
            await self.update_summary_result(summary.id, full_text, knowledge_points)

            yield {
                "type": "done",
                "summary_id": summary.id,
                "mode": mode,
            }
        except Exception as e:
            logger.error(f"总结生成失败: {e}")
            yield {"type": "error", "message": f"AI 服务暂时不可用: {str(e)}"}

    async def list_summaries(
        self, user_id: str, page: int = 1, page_size: int = 20, mode: str | None = None,
    ) -> tuple[list[Summary], int]:
        """获取用户的总结历史（按时间倒序，可分页和筛选）"""
        # 总数
        conditions = [Summary.user_id == user_id]
        if mode:
            conditions.append(Summary.mode == mode)
        count_stmt = select(func.count()).select_from(Summary).where(*conditions)
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 分页
=======
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
            response = await llm_client.chat(
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
>>>>>>> main
        stmt = (
            select(Summary)
            .where(*conditions)
            .order_by(Summary.created_at.desc())
<<<<<<< HEAD
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        summaries = list(result.scalars().all())
        return summaries, total

    async def get_summary(self, summary_id: str, user_id: str) -> Summary | None:
        """获取单条总结详情"""
        summary = await self.db.get(Summary, summary_id)
        if summary and summary.user_id == user_id:
            return summary
        return None

    async def delete_summary(self, summary_id: str, user_id: str) -> bool:
        """删除总结记录"""
        summary = await self.db.get(Summary, summary_id)
        if not summary or summary.user_id != user_id:
            return False
        await self.db.delete(summary)
        await self.db.flush()
        return True

    @staticmethod
    def _extract_knowledge_points(text: str) -> list[str]:
        """从总结文本中简单提取知识点（后续可改用 LLM 提取）"""
        points = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "• ", "* ", "· ")):
                point = line.lstrip("- •*·").strip()
                if point and len(point) > 1:
                    points.append(point)
        return points[:10]
=======
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
>>>>>>> main
