"""智能教案生成模块 — 业务逻辑层 (PBI_LP)"""

import uuid
from typing import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from loguru import logger

from app.models.lesson_plan import LessonPlan
from app.schemas.lesson_plan import (
    GenerateLessonPlanRequest,
    LessonPlanItem,
    LessonPlanDetailResponse,
    LessonPlanListResponse,
    LessonPlanSection,
)
from app.ai.llm_client import llm_client
from app.ai.prompts.lesson_plan import (
    SYSTEM_PROMPT,
    LESSON_PLAN_TEMPLATE,
    EXTRA_CLASS_HOUR_TEMPLATE,
    TITLE_EXTRACTION_TEMPLATE,
)
from app.core.utils import sse_json, truncate


class LessonPlanService:
    """智能教案生成服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─────────────────────────────────────────────────────
    # 核心：流式生成教案
    # ─────────────────────────────────────────────────────

    async def generate_stream(
        self,
        request: GenerateLessonPlanRequest,
        user_id: str,
    ) -> AsyncIterator[str]:
        """
        SSE 流式生成教案。
        每个 yield 返回一行 SSE 格式的 JSON 字符串（不含 'data: ' 前缀）。
        """
        try:
            async for event in self._generate_stream_impl(request, user_id):
                yield event
        except Exception as e:
            logger.error(f"教案生成异常 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"教案生成服务异常: {str(e)}"})

    async def _generate_stream_impl(
        self,
        request: GenerateLessonPlanRequest,
        user_id: str,
    ) -> AsyncIterator[str]:
        """
        SSE 流式生成教案实现。
        每个 yield 返回一行 SSE 格式的 JSON 字符串（不含 'data: ' 前缀）。
        """
        # 1. 构建多课时扩展内容
        extra_hours_text = ""
        if request.class_hours > 1:
            extra_parts = []
            for i in range(2, request.class_hours + 1):
                extra_parts.append(
                    EXTRA_CLASS_HOUR_TEMPLATE.format(class_number=i)
                )
            extra_hours_text = "\n".join(extra_parts)

        # 2. 构建 requirements 段落
        requirements_section = ""
        if request.requirements and request.requirements.strip():
            requirements_section = f"- **特殊要求**：{request.requirements.strip()}"

        # 3. 构建 Prompt
        user_prompt = LESSON_PLAN_TEMPLATE.format(
            subject=request.subject,
            grade=request.grade,
            textbook_version=request.textbook_version or "未指定",
            unit_chapter=request.unit_chapter or "未指定",
            class_hours=request.class_hours,
            teaching_objectives=request.teaching_objectives,
            requirements_section=requirements_section,
            extra_class_hours=extra_hours_text,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 4. 流式调用 LLM
        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(messages, temperature=0.7):
                full_text += chunk
                yield sse_json({"type": "content", "chunk": chunk})
        except Exception as e:
            logger.error(f"LLM 流式调用失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"AI 服务调用失败: {str(e)}"})
            return

        # 5. 提取标题
        title = await self._extract_title(full_text)

        # 6. 提取结构化分段
        sections = self._parse_sections(full_text)

        # 7. 持久化到数据库
        lesson_plan = LessonPlan(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            subject=request.subject,
            grade=request.grade,
            textbook_version=request.textbook_version or "",
            unit_chapter=request.unit_chapter or "",
            class_hours=request.class_hours,
            teaching_objectives=request.teaching_objectives,
            requirements=request.requirements,
            plan_content=full_text,
            sections=[s.model_dump() for s in sections],
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(lesson_plan)
        await self.db.flush()

        logger.info(
            f"教案已保存 | lesson_plan_id={lesson_plan.id} | user={user_id} "
            f"| subject={request.subject} | grade={request.grade} | len={len(full_text)}"
        )

        # 8. 完成事件
        yield sse_json({
            "type": "done",
            "lesson_plan_id": lesson_plan.id,
            "title": title,
        })

    # ─────────────────────────────────────────────────────
    # 标题提取
    # ─────────────────────────────────────────────────────

    async def _extract_title(self, plan_content: str) -> str:
        """从教案内容中提取标题"""
        try:
            # 先尝试从 Markdown 中直接提取 # 标题
            for line in plan_content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    return stripped[2:].strip()

            # 如果没找到，使用 LLM 提取
            preview = plan_content[:500]
            prompt = TITLE_EXTRACTION_TEMPLATE.format(content_preview=preview)
            messages = [
                {"role": "system", "content": "你是一个文本标题提取助手。请只返回标题文本。"},
                {"role": "user", "content": prompt},
            ]
            response = await llm_client.chat(
                messages, temperature=0.3, max_tokens=64
            )
            title = response.strip().strip('"').strip("'").strip()
            return title if title else "未命名教案"
        except Exception as e:
            logger.warning(f"标题提取失败，使用默认标题: {e}")

        return "未命名教案"

    # ─────────────────────────────────────────────────────
    # 结构化分段解析
    # ─────────────────────────────────────────────────────

    def _parse_sections(self, plan_content: str) -> list[LessonPlanSection]:
        """从 Markdown 教案中解析结构化分段（非 AI 方式，正则提取标题）"""
        import re
        sections = []
        # 匹配 ## 二级标题及其后续内容
        pattern = r"##\s+(.+?)\n(.*?)(?=\n##\s|\Z)"
        matches = re.findall(pattern, plan_content, re.DOTALL)
        for title, content in matches:
            sections.append(
                LessonPlanSection(title=title.strip(), content=content.strip())
            )
        return sections

    # ─────────────────────────────────────────────────────
    # 查询：历史列表
    # ─────────────────────────────────────────────────────

    async def list_lesson_plans(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> LessonPlanListResponse:
        """分页查询历史教案记录"""
        conditions = [LessonPlan.user_id == user_id]

        # 总数
        count_stmt = select(func.count()).select_from(LessonPlan).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        stmt = (
            select(LessonPlan)
            .where(*conditions)
            .order_by(LessonPlan.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [
            LessonPlanItem(
                id=row.id,
                title=row.title,
                subject=row.subject,
                grade=row.grade,
                textbook_version=row.textbook_version,
                unit_chapter=row.unit_chapter,
                class_hours=row.class_hours,
                plan_content=truncate(row.plan_content, 300),
                created_at=row.created_at,
            )
            for row in rows
        ]

        total_pages = max(1, (total + page_size - 1) // page_size)

        return LessonPlanListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # ─────────────────────────────────────────────────────
    # 查询：单条详情
    # ─────────────────────────────────────────────────────

    async def get_lesson_plan(
        self, user_id: str, lesson_plan_id: str
    ) -> LessonPlanDetailResponse | None:
        """查看单条教案详情"""
        stmt = select(LessonPlan).where(
            LessonPlan.id == lesson_plan_id,
            LessonPlan.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        sections = [
            LessonPlanSection(**s) for s in (row.sections or [])
        ]

        return LessonPlanDetailResponse(
            id=row.id,
            title=row.title,
            subject=row.subject,
            grade=row.grade,
            textbook_version=row.textbook_version,
            unit_chapter=row.unit_chapter,
            class_hours=row.class_hours,
            teaching_objectives=row.teaching_objectives,
            requirements=row.requirements,
            plan_content=row.plan_content,
            sections=sections,
            created_at=row.created_at,
        )

    # ─────────────────────────────────────────────────────
    # 删除
    # ─────────────────────────────────────────────────────

    async def delete_lesson_plan(self, user_id: str, lesson_plan_id: str) -> bool:
        """删除一条教案记录（软性校验归属）"""
        stmt = delete(LessonPlan).where(
            LessonPlan.id == lesson_plan_id,
            LessonPlan.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(
                f"教案已删除 | lesson_plan_id={lesson_plan_id} | user={user_id}"
            )
        return deleted
