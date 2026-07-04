"""
习题服务层 (PBI_08, PBI_09, PBI_10) — 习题生成、批改、历史记录
"""

import json
import re
import uuid
from datetime import datetime

from loguru import logger
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.exercise_gen import EXERCISE_GEN_SYSTEM_PROMPT, EXERCISE_GEN_USER_TEMPLATE
from app.ai.prompts.grading import GRADING_SYSTEM_PROMPT, GRADING_USER_TEMPLATE
from app.models.exercise import Exercise, ExerciseAttempt
from app.schemas.exercise import (
    AnswerItem,
    Difficulty,
    ExerciseItem,
    GenerateExerciseReq,
    GradeReq,
    GradeResp,
    GradedItem,
    QuestionType,
)


class ExerciseService:
    """习题业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 习题生成 (PBI_08) ──────────────────────────────────────

    async def generate(
        self, user_id: str, req: GenerateExerciseReq
    ) -> tuple[str, list[Exercise]]:
        """
        调用LLM生成习题 → 解析 → 入库 → 返回 (batch_id, exercises)

        Raises:
            ValueError: LLM 返回内容无法解析为合法习题列表
        """
        batch_id = str(uuid.uuid4())

        # 构建 Prompt
        user_prompt = EXERCISE_GEN_USER_TEMPLATE.format(
            count=req.count,
            subject=req.subject,
            grade=req.grade,
            knowledge_points="、".join(req.knowledge_points),
            difficulty=req.difficulty.value
            if isinstance(req.difficulty, Difficulty)
            else req.difficulty,
            question_types="、".join(
                qt.value if isinstance(qt, QuestionType) else qt
                for qt in req.question_types
            ),
        )

        messages = [
            {"role": "system", "content": EXERCISE_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(
            f"用户 {user_id} 请求生成习题 | 学科={req.subject} | 年级={req.grade} "
            f"| 知识点={req.knowledge_points} | 数量={req.count} | 难度={req.difficulty}"
        )

        # 调用 LLM
        raw = await llm_client.chat_with_retry(messages)
        exercises_data = self._parse_llm_json(raw)

        # 校验并入库
        if not exercises_data:
            raise ValueError("LLM 未返回有效习题数据")

        exercises = []
        for item in exercises_data:
            if not item.get("question"):
                logger.warning(f"跳过无 question 字段的习题: {item}")
                continue

            exercise = Exercise(
                user_id=user_id,
                batch_id=batch_id,
                subject=req.subject,
                grade=req.grade,
                question_type=item.get(
                    "question_type", req.question_types[0].value
                    if isinstance(req.question_types[0], QuestionType)
                    else req.question_types[0]
                ),
                question=item["question"],
                options=item.get("options"),
                answer=item.get("answer", ""),
                analysis=item.get("analysis", ""),
                difficulty=item.get(
                    "difficulty",
                    req.difficulty.value
                    if isinstance(req.difficulty, Difficulty)
                    else req.difficulty,
                ),
                knowledge_points=item.get(
                    "knowledge_points", req.knowledge_points
                ),
            )
            self.db.add(exercise)
            exercises.append(exercise)

        if not exercises:
            raise ValueError("LLM 返回的数据中没有有效习题")

        await self.db.flush()
        logger.info(
            f"成功生成 {len(exercises)} 道习题 | batch_id={batch_id}"
        )
        return batch_id, exercises

    # ── 习题批改 (PBI_10) ──────────────────────────────────────

    async def grade(self, user_id: str, req: GradeReq) -> GradeResp:
        """
        批改作答：加载习题 → 构建批改 Prompt → LLM 判分 → 存储作答记录

        Returns:
            GradeResp: 包含每题得分、正确率、纠错建议
        """
        exercise_ids = [a.exercise_id for a in req.answers]
        stmt = select(Exercise).where(
            and_(Exercise.id.in_(exercise_ids), Exercise.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        exercises_map: dict[str, Exercise] = {
            e.id: e for e in result.scalars().all()
        }

        if not exercises_map:
            raise ValueError("未找到需要批改的习题")

        # 构建 LLM 批改输入（仅提交存在的题目）
        answers_for_llm = []
        valid_answers: list[AnswerItem] = []
        for ans in req.answers:
            ex = exercises_map.get(ans.exercise_id)
            if not ex:
                logger.warning(
                    f"忽略不存在的习题 | exercise_id={ans.exercise_id}"
                )
                continue
            answers_for_llm.append(
                {
                    "exercise_id": ans.exercise_id,
                    "question": ex.question,
                    "question_type": ex.question_type,
                    "options": ex.options,
                    "correct_answer": ex.answer,
                    "analysis": ex.analysis,
                    "user_answer": ans.user_answer,
                }
            )
            valid_answers.append(ans)

        if not answers_for_llm:
            raise ValueError("提交的作答中没有可批改的习题")

        grading_prompt = GRADING_USER_TEMPLATE.format(
            answers_json=json.dumps(answers_for_llm, ensure_ascii=False)
        )

        messages = [
            {"role": "system", "content": GRADING_SYSTEM_PROMPT},
            {"role": "user", "content": grading_prompt},
        ]

        logger.info(
            f"用户 {user_id} 提交批改 | 题目数={len(answers_for_llm)}"
        )
        raw = await llm_client.chat_with_retry(messages)
        graded_data = self._parse_llm_json(raw)

        # 存储作答记录 & 汇总结果
        total_score = 0.0
        correct_count = 0
        results: list[GradedItem] = []

        for item in graded_data:
            eid = item.get("exercise_id", "")
            is_correct = bool(item.get("is_correct", False))
            score = float(item.get("score", 0))

            # 存储作答记录
            matched_answer = next(
                (a for a in valid_answers if a.exercise_id == eid), None
            )
            attempt = ExerciseAttempt(
                user_id=user_id,
                exercise_id=eid,
                user_answer=matched_answer.user_answer if matched_answer else "",
                is_correct=is_correct,
                score=score,
                graded_by="auto",
            )
            self.db.add(attempt)

            total_score += score
            if is_correct:
                correct_count += 1

            results.append(
                GradedItem(
                    exercise_id=eid,
                    is_correct=is_correct,
                    score=score,
                    correct_answer=item.get("correct_answer", ""),
                    analysis=item.get("analysis", ""),
                    error_reason=item.get("error_reason"),
                    related_knowledge=item.get("related_knowledge", []),
                )
            )

        await self.db.flush()
        logger.info(
            f"批改完成 | 总分={total_score:.1f} | "
            f"正确={correct_count}/{len(results)}"
        )

        return GradeResp(
            total_score=total_score,
            correct_count=correct_count,
            total_count=len(results),
            results=results,
        )

    # ── 做题历史 (PBI_09) ──────────────────────────────────────

    async def get_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        subject: str | None = None,
        grade: str | None = None,
    ) -> dict:
        """
        获取做题历史 — 按批次分组，最新在前

        Returns:
            dict: {items, total, page, page_size, total_pages}
        """
        conditions = [Exercise.user_id == user_id]
        if subject:
            conditions.append(Exercise.subject == subject)
        if grade:
            conditions.append(Exercise.grade == grade)

        # 子查询：每个批次一行
        subq = (
            select(
                Exercise.batch_id,
                func.max(Exercise.subject).label("subject"),
                func.max(Exercise.grade).label("grade"),
                func.count().label("exercise_count"),
                func.max(Exercise.created_at).label("created_at"),
            )
            .where(and_(*conditions))
            .group_by(Exercise.batch_id)
            .subquery()
        )

        # 总数
        total = (
            await self.db.execute(select(func.count()).select_from(subq))
        ).scalar() or 0

        # 分页取批次
        offset = (page - 1) * page_size
        batch_rows = (
            await self.db.execute(
                select(subq)
                .order_by(subq.c.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).all()

        items = []
        if batch_rows:
            batch_ids = [r.batch_id for r in batch_rows]

            # 一次查询取回所有批次的题型
            qt_result = (
                await self.db.execute(
                    select(Exercise.batch_id, Exercise.question_type).where(
                        Exercise.batch_id.in_(batch_ids)
                    )
                )
            ).all()

            qt_map: dict[str, set] = {}
            for bid, qt in qt_result:
                qt_map.setdefault(bid, set()).add(qt)

            for row in batch_rows:
                items.append(
                    {
                        "batch_id": row.batch_id,
                        "subject": row.subject,
                        "grade": row.grade,
                        "question_types": sorted(
                            qt_map.get(row.batch_id, set())
                        ),
                        "count": row.exercise_count,
                        "created_at": row.created_at.isoformat()
                        if row.created_at
                        else None,
                    }
                )

        total_pages = (
            (total + page_size - 1) // page_size if page_size else 1
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ── 批次详情 ────────────────────────────────────────────────

    async def get_batch_detail(
        self, user_id: str, batch_id: str
    ) -> dict | None:
        """
        获取批次详情 — 包含习题列表及作答记录

        Returns:
            dict | None: 批次详情，不存在时返回 None
        """
        stmt = (
            select(Exercise)
            .where(
                and_(Exercise.user_id == user_id, Exercise.batch_id == batch_id)
            )
            .order_by(Exercise.created_at)
        )
        result = await self.db.execute(stmt)
        exercises = result.scalars().all()

        if not exercises:
            return None

        # 取作答记录
        exercise_ids = [e.id for e in exercises]
        attempts_stmt = select(ExerciseAttempt).where(
            and_(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.exercise_id.in_(exercise_ids),
            )
        )
        attempts_result = await self.db.execute(attempts_stmt)
        attempts_map = {
            a.exercise_id: a for a in attempts_result.scalars().all()
        }

        exercise_items = []
        for ex in exercises:
            attempt = attempts_map.get(ex.id)
            exercise_items.append(
                {
                    "id": ex.id,
                    "question": ex.question,
                    "question_type": ex.question_type,
                    "options": ex.options,
                    "answer": ex.answer,
                    "analysis": ex.analysis,
                    "difficulty": ex.difficulty,
                    "knowledge_points": ex.knowledge_points,
                    "user_answer": attempt.user_answer if attempt else None,
                    "is_correct": attempt.is_correct if attempt else None,
                    "score": attempt.score if attempt else None,
                }
            )

        return {
            "batch_id": batch_id,
            "subject": exercises[0].subject,
            "grade": exercises[0].grade,
            "created_at": exercises[0].created_at.isoformat()
            if exercises[0].created_at
            else None,
            "exercises": exercise_items,
        }

    # ── 删除批次 ────────────────────────────────────────────────

    async def delete_batch(self, user_id: str, batch_id: str) -> int:
        """
        删除一个批次的所有习题（级联删除作答记录）

        Returns:
            int: 删除的习题数量，0 表示该批次不存在或无权限
        """
        stmt = delete(Exercise).where(
            and_(Exercise.user_id == user_id, Exercise.batch_id == batch_id)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        if result.rowcount:
            logger.info(
                f"用户 {user_id} 删除批次 | batch_id={batch_id} | "
                f"共 {result.rowcount} 道习题"
            )
        return result.rowcount

    # ── 工具方法 ────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_json(raw: str) -> list[dict]:
        """
        解析 LLM 返回的 JSON — 兼容 markdown 代码块包裹和常见格式异常

        Raises:
            ValueError: 无法解析为合法列表
        """
        raw = raw.strip()

        # 去除 markdown 代码块标记
        if raw.startswith("```"):
            lines = raw.split("\n")
            # 去掉开头的 ```json 或 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 去掉结尾的 ```
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    raise ValueError(
                        f"无法解析 LLM 返回的 JSON: {raw[:500]}"
                    )
            else:
                raise ValueError(
                    f"LLM 返回中未找到 JSON 数组: {raw[:500]}"
                )

        # 统一转为列表
        if isinstance(data, dict):
            # 可能包裹在常见 key 中
            for key in ("exercises", "data", "items", "results"):
                if key in data:
                    return data[key]
            # 单个习题对象
            return [data]

        if isinstance(data, list):
            return data

        raise ValueError(f"LLM 返回格式异常（非列表/字典）: {raw[:500]}")
