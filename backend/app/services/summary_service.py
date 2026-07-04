"""
课文总结服务层 (PBI_06)
"""

import json
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.summary import (
    BRIEF_PROMPT_TEMPLATE,
    DETAILED_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
)
from app.models.summary import Summary


class SummaryService:
    """课文总结业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
        stmt = (
            select(Summary)
            .where(*conditions)
            .order_by(Summary.created_at.desc())
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
