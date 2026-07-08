"""试卷生成器 — 业务逻辑层 (功能2)"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.exam_paper import ExamPaper
from app.models.teaching_resource import TeachingResource
from app.schemas.exam_paper import (
    ExamPaperGenerateRequest,
    ExamPaperItem,
    ExamPaperDetail,
    ExamPaperListResponse,
    ExamPaperContent,
    ExamPaperContentHeader,
    ExamPaperSection,
    ExamPaperQuestion,
    ExamPaperStatus,
    ExamPaperAnswerSheet,
    ExportFormat,
    QuestionTypeConfig,
)
from app.ai.llm_client import llm_client
from app.ai.prompts.exam_paper import (
    EXAM_PAPER_SYSTEM_PROMPT,
    EXAM_PAPER_USER_TEMPLATE,
    SUBJECT_INSTRUCTIONS,
    EXAM_TYPE_NAMES,
)
from app.core.utils import sse_json, truncate, extract_json


class ExamPaperService:
    """试卷生成服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─────────────────────────────────────────────────────
    # 辅助：获取教学资源库文件引用上下文
    # ─────────────────────────────────────────────────────

    async def _get_resource_context(self, resource_id: str) -> str:
        """从教学资源库读取文件信息，构建注入 Prompt 的参考上下文"""
        stmt = select(TeachingResource).where(TeachingResource.id == resource_id)
        result = await self.db.execute(stmt)
        resource = result.scalar_one_or_none()

        if not resource:
            logger.warning(f"试卷生成引用了不存在的资源 | resource_id={resource_id}")
            return ""

        lines = [
            "\n---",
            "## 参考教学资源",
            f"- **资源标题**：{resource.title}",
        ]
        if resource.description:
            lines.append(f"- **资源描述**：{resource.description}")
        if resource.subject:
            lines.append(f"- **所属学科**：{resource.subject}")
        if resource.grade:
            lines.append(f"- **适用年级**：{resource.grade}")
        if resource.tags:
            lines.append(f"- **标签**：{', '.join(resource.tags)}")
        if resource.resource_type:
            type_map = {"courseware": "课件", "exam_paper": "试卷", "lesson_plan": "教案", "other": "其他"}
            lines.append(f"- **资源类型**：{type_map.get(resource.resource_type, resource.resource_type)}")

        # 尝试读取文本文件内容
        text_exts = {".txt", ".md", ".csv", ".json", ".html", ".xml", ".yaml", ".yml"}
        ext = (resource.file_ext or "").lower()
        if ext in text_exts:
            try:
                import os
                file_path = resource.file_path
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(8000)
                    if content.strip():
                        lines.append(f"\n### 文件内容预览（前8000字）\n```\n{content}\n```")
                else:
                    logger.warning(f"资源文件不存在 | path={file_path}")
            except Exception as e:
                logger.warning(f"读取资源文件内容失败 | resource_id={resource_id} | error={e}")

        lines.append("\n---")
        lines.append("**请结合以上参考教学资源命题，确保试题内容与参考资料相关。**")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────
    # 核心：SSE 流式生成试卷
    # ─────────────────────────────────────────────────────

    async def generate_exam_paper_sse(
        self,
        user_id: str,
        req: ExamPaperGenerateRequest,
    ) -> AsyncIterator[str]:
        """
        SSE 流式生成试卷。
        每个 yield 返回一行 SSE 格式的 JSON 字符串（不含 'data: ' 前缀）。
        """
        # 1. 获取教学资源引用上下文
        resource_context = ""
        if req.resource_id:
            resource_context = await self._get_resource_context(req.resource_id)

        # 2. 构建 User Prompt
        user_prompt = await self._build_user_message(req, resource_context)
        messages = [
            {"role": "system", "content": EXAM_PAPER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 3. 发送开始思考事件
        yield sse_json({"type": "thinking", "stage": "analyzing", "message": "正在分析试卷配置和要求..."})

        # 4. 流式调用 LLM
        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(
                messages, temperature=0.6, max_tokens=16384
            ):
                full_text += chunk
                yield sse_json({"type": "content", "chunk": chunk})
        except Exception as e:
            logger.error(f"LLM 流式调用失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"AI 服务调用失败: {str(e)}"})
            return

        # 4. 解析 JSON 试卷内容
        yield sse_json({"type": "progress", "stage": "parsing", "message": "正在解析试卷内容..."})

        try:
            json_match = extract_json(full_text)
            if not json_match:
                raise ValueError("无法从AI回复中提取JSON试卷数据")

            try:
                content_data = json.loads(json_match)
            except json.JSONDecodeError:
                # 尝试修复 LaTeX 转义问题
                fixed = json_match
                fixed = re.sub(r'\\([a-zA-Z]+)', r'\\\\\1', fixed)
                try:
                    content_data = json.loads(fixed)
                    logger.info(f"LaTeX转义修复成功 | user={user_id}")
                except json.JSONDecodeError as e2:
                    raise ValueError(f"JSON解析失败（已尝试LaTeX转义修复）: {e2}")

            # 验证必需字段
            if "header" not in content_data:
                raise ValueError("试卷数据缺少 header 字段")
            if "sections" not in content_data:
                raise ValueError("试卷数据缺少 sections 字段")

        except Exception as e:
            logger.error(f"试卷JSON解析失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"试卷数据解析失败: {str(e)}"})
            return

        # 5. 生成答题卡（服务端自动构建，不依赖AI）
        yield sse_json({"type": "progress", "stage": "answer_sheet", "message": "正在生成答题卡..."})
        answer_sheet = self._generate_answer_sheet(content_data)

        # 6. 构建试卷正文结构化数据
        content_full = self._build_content_from_data(content_data)

        # 7. 持久化到数据库
        paper = ExamPaper(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=req.title,
            subject=req.subject,
            grade=req.grade,
            exam_type=req.exam_type.value,
            total_score=req.total_score,
            difficulty_ratio=req.difficulty_ratio,
            question_structure=[qs.model_dump() for qs in req.question_structure],
            content=content_full.model_dump(),
            answer_sheet=answer_sheet.model_dump(),
            status=ExamPaperStatus.COMPLETED.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(paper)
        await self.db.flush()

        logger.info(
            f"试卷已保存 | paper_id={paper.id} | user={user_id} | "
            f"subject={req.subject} | score={req.total_score}"
        )

        # 8. 完成事件
        yield sse_json({
            "type": "done",
            "paper_id": paper.id,
            "title": req.title,
        })

    # ─────────────────────────────────────────────────────
    # 构建 User Message
    # ─────────────────────────────────────────────────────

    async def _build_user_message(self, req: ExamPaperGenerateRequest, resource_context: str = "") -> str:
        """将题型分布转化为文本描述"""
        # 题型分布文本
        structure_lines = []
        for qs in req.question_structure:
            structure_lines.append(
                f"- {qs.type}：{qs.count}道题，每题{qs.score_per}分，共{qs.subtotal}分"
            )
        structure_text = "\n".join(structure_lines)

        # 考试类型中文名
        exam_type_name = EXAM_TYPE_NAMES.get(req.exam_type.value, req.exam_type.value)

        # 学科特定提示
        subject_instruction = SUBJECT_INSTRUCTIONS.get(req.subject, "请按照该学科的课程标准命题。")

        # 补充说明
        focus_text = ""
        if req.focus_instruction and req.focus_instruction.strip():
            focus_text = f"\n## 特别关注\n{req.focus_instruction.strip()}"

        return EXAM_PAPER_USER_TEMPLATE.format(
            title=req.title,
            subject=req.subject,
            grade=req.grade,
            exam_type=exam_type_name,
            total_score=req.total_score,
            question_structure_text=structure_text,
            easy_ratio=req.difficulty_ratio.get("easy", 30),
            medium_ratio=req.difficulty_ratio.get("medium", 50),
            hard_ratio=req.difficulty_ratio.get("hard", 20),
            subject_instruction=subject_instruction,
            focus_instruction=focus_text,
            resource_context=resource_context,
        )

    # ─────────────────────────────────────────────────────
    # 解析 AI 回复构建结构化数据
    # ─────────────────────────────────────────────────────

    def _build_content_from_data(self, data: dict) -> ExamPaperContent:
        """将AI返回的JSON数据转换为ExamPaperContent"""
        header_data = data.get("header", {})
        header = ExamPaperContentHeader(
            title=header_data.get("title", ""),
            subject=header_data.get("subject", ""),
            grade=header_data.get("grade", ""),
            exam_type=header_data.get("exam_type", ""),
            total_score=header_data.get("total_score", 0),
            duration_minutes=header_data.get("duration_minutes", 120),
            instructions=header_data.get("instructions", ""),
        )

        sections = []
        for sec_data in data.get("sections", []):
            questions = []
            for q_data in sec_data.get("questions", []):
                questions.append(ExamPaperQuestion(
                    number=q_data.get("number", 0),
                    stem=q_data.get("stem", ""),
                    question_type=q_data.get("question_type", ""),
                    options=q_data.get("options"),
                    answer=q_data.get("answer", ""),
                    score=q_data.get("score", 0),
                    analysis=q_data.get("analysis", ""),
                    knowledge_points=q_data.get("knowledge_points", []),
                ))
            sections.append(ExamPaperSection(
                title=sec_data.get("title", ""),
                instructions=sec_data.get("instructions", ""),
                questions=questions,
            ))

        return ExamPaperContent(
            header=header,
            sections=sections,
            answer_key=data.get("answer_key", []),
            scoring_guide=data.get("scoring_guide", ""),
        )

    # ─────────────────────────────────────────────────────
    # 答题卡自动生成（服务端构建，不依赖AI）
    # ─────────────────────────────────────────────────────

    def _generate_answer_sheet(self, content_data: dict) -> ExamPaperAnswerSheet:
        """
        根据试卷内容自动构建答题卡。
        选择题填涂区、填空题作答区、简答/综合留白区。
        """
        header = content_data.get("header", {})
        paper_id = ""  # 将在保存后填充
        title = header.get("title", "答题卡")

        sheet_sections = []

        for sec_data in content_data.get("sections", []):
            sec_title = sec_data.get("title", "")
            questions = sec_data.get("questions", [])

            sheet_questions = []
            for q in questions:
                q_type = q.get("question_type", "")
                q_entry = {
                    "number": q.get("number", 0),
                    "question_type": q_type,
                    "score": q.get("score", 0),
                }

                if q_type == "choice":
                    # 选择题：提供ABCD填涂区
                    q_entry["answer_area"] = {
                        "type": "bubble",
                        "options": q.get("options", ["A", "B", "C", "D"]),
                    }
                elif q_type in ("fill", "fill_blank"):
                    # 填空题：留白作答区
                    q_entry["answer_area"] = {
                        "type": "blank",
                        "lines": 2,
                    }
                elif q_type in ("short_answer", "calculation"):
                    # 简答/计算题：预留5行作答区
                    q_entry["answer_area"] = {
                        "type": "lined",
                        "lines": 6,
                    }
                elif q_type in ("comprehensive", "analysis"):
                    # 综合题/分析题：预留10行作答区
                    q_entry["answer_area"] = {
                        "type": "lined",
                        "lines": 12,
                    }
                else:
                    # 默认留白
                    q_entry["answer_area"] = {
                        "type": "lined",
                        "lines": 5,
                    }

                sheet_questions.append(q_entry)

            sheet_sections.append({
                "title": sec_title,
                "questions": sheet_questions,
            })

        return ExamPaperAnswerSheet(
            paper_id=paper_id,
            title=f"{title} — 答题卡",
            student_info={
                "name": "",
                "class": "",
                "student_id": "",
            },
            sections=sheet_sections,
        )

    # ─────────────────────────────────────────────────────
    # 查询：历史列表
    # ─────────────────────────────────────────────────────

    async def list_exam_papers(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        subject: str | None = None,
        exam_type: str | None = None,
    ) -> ExamPaperListResponse:
        """分页查询历史试卷记录"""
        conditions = [ExamPaper.user_id == user_id]
        if subject:
            conditions.append(ExamPaper.subject == subject)
        if exam_type:
            conditions.append(ExamPaper.exam_type == exam_type)

        # 总数
        count_stmt = select(func.count()).select_from(ExamPaper).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        stmt = (
            select(ExamPaper)
            .where(*conditions)
            .order_by(ExamPaper.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for row in rows:
            content = row.content or {}
            question_count = 0
            for sec in content.get("sections", []):
                question_count += len(sec.get("questions", []))

            items.append(ExamPaperItem(
                id=row.id,
                title=row.title,
                subject=row.subject,
                grade=row.grade,
                exam_type=row.exam_type,
                total_score=row.total_score,
                status=ExamPaperStatus(row.status),
                question_count=question_count,
                created_at=row.created_at,
            ))

        total_pages = max(1, (total + page_size - 1) // page_size)

        return ExamPaperListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # ─────────────────────────────────────────────────────
    # 查询：单条详情
    # ─────────────────────────────────────────────────────

    async def get_detail(self, user_id: str, paper_id: str) -> ExamPaperDetail | None:
        """查看试卷详情"""
        stmt = select(ExamPaper).where(
            ExamPaper.id == paper_id,
            ExamPaper.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        return ExamPaperDetail(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            subject=row.subject,
            grade=row.grade,
            exam_type=row.exam_type,
            total_score=row.total_score,
            difficulty_ratio=row.difficulty_ratio or {},
            question_structure=row.question_structure or [],
            content=ExamPaperContent(**row.content) if row.content else None,
            answer_sheet=row.answer_sheet,
            export_url=row.export_url,
            export_format=row.export_format,
            status=ExamPaperStatus(row.status),
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    # ─────────────────────────────────────────────────────
    # 删除
    # ─────────────────────────────────────────────────────

    async def delete(self, user_id: str, paper_id: str) -> bool:
        """删除一条试卷记录"""
        stmt = delete(ExamPaper).where(
            ExamPaper.id == paper_id,
            ExamPaper.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"试卷已删除 | paper_id={paper_id} | user={user_id}")
        return deleted

    # ─────────────────────────────────────────────────────
    # 导出（调用 ExportService）
    # ─────────────────────────────────────────────────────

    async def export_paper(
        self,
        user_id: str,
        paper_id: str,
        export_format: ExportFormat,
    ) -> tuple[str, str] | None:
        """
        导出试卷，返回 (文件路径, 文件名)。
        """
        stmt = select(ExamPaper).where(
            ExamPaper.id == paper_id,
            ExamPaper.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        from app.services.export_service import ExportService

        export_service = ExportService()
        file_path, file_name = export_service.export_exam_paper(
            paper_data=row,
            export_format=export_format,
        )

        # 更新数据库中的导出信息
        row.export_url = file_path
        row.export_format = export_format.value
        row.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"试卷已导出 | paper_id={paper_id} | format={export_format.value}")
        return file_path, file_name
