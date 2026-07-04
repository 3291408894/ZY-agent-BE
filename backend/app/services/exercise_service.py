"""
习题服务层 (PBI_08, PBI_09, PBI_10)
"""

import json
import uuid
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.exercise_gen import (
    EXERCISE_GEN_SYSTEM_PROMPT,
    EXERCISE_GEN_USER_TEMPLATE,
)
from app.ai.prompts.grading import (
    GRADING_SYSTEM_PROMPT,
    GRADING_USER_TEMPLATE,
)
from app.models.exercise import Exercise, ExerciseBatch, ExerciseAttempt


class ExerciseService:
    """习题业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_stream(
        self,
        user_id: str,
        subject: str,
        grade: str,
        knowledge_points: list[str],
        difficulty: str = "medium",
        question_types: list[str] | None = None,
        count: int = 5,
    ) -> AsyncIterator[dict]:
        """SSE 流式生成习题 — 逐题返回 + 进度条，且 answer/analysis 在生成阶段为 null"""
        if question_types is None:
            question_types = ["choice"]

        # 先生成 batch_id，创建批次记录
        batch_id = str(uuid.uuid4())
        batch = ExerciseBatch(
            id=batch_id,
            user_id=user_id,
            subject=subject,
            grade=grade,
            total_count=count,
            status="pending",
        )
        self.db.add(batch)
        await self.db.flush()

        yield {"type": "meta", "batch_id": batch_id}

        user_prompt = EXERCISE_GEN_USER_TEMPLATE.format(
            count=count,
            subject=subject,
            grade=grade,
            knowledge_points=", ".join(knowledge_points),
            difficulty=difficulty,
            question_types=", ".join(question_types),
        )
        messages = [
            {"role": "system", "content": EXERCISE_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(messages):
                full_text += chunk

            # 解析 LLM 返回的 JSON 习题列表
            exercises_data = self._parse_exercises_json(full_text)
            saved_exercises = []

            for i, ex_data in enumerate(exercises_data):
                exercise = Exercise(
                    user_id=user_id,
                    subject=subject,
                    grade=grade,
                    question_type=ex_data.get("question_type", "choice"),
                    question=ex_data.get("question", ""),
                    options=ex_data.get("options"),
                    answer=ex_data.get("answer", ""),  # 仍然存 DB
                    analysis=ex_data.get("analysis", ""),
                    difficulty=difficulty,
                    knowledge_points=ex_data.get("knowledge_points", knowledge_points),
                )
                self.db.add(exercise)
                await self.db.flush()
                saved_exercises.append(exercise)

                # 逐题 yield — 但不暴露 answer 和 analysis
                yield {
                    "type": "exercise",
                    "exercise": {
                        "id": exercise.id,
                        "question": exercise.question,
                        "question_type": exercise.question_type,
                        "options": exercise.options,
                        "answer": None,         # PBI 要求：生成阶段不泄露答案
                        "analysis": None,
                        "difficulty": exercise.difficulty,
                        "knowledge_points": exercise.knowledge_points,
                        "subject": exercise.subject,
                        "grade": exercise.grade,
                    },
                }
                yield {"type": "progress", "generated": i + 1, "total": count}

            # 更新批次状态
            batch.status = "doing"
            batch.total_count = len(saved_exercises)
            self.db.add(batch)
            await self.db.flush()

            yield {
                "type": "done",
                "batch_id": batch_id,
                "exercises": [
                    {
                        "id": ex.id,
                        "question": ex.question,
                        "question_type": ex.question_type,
                        "options": ex.options,
                        "answer": None,
                        "analysis": None,
                        "difficulty": ex.difficulty,
                        "knowledge_points": ex.knowledge_points,
                        "subject": ex.subject,
                        "grade": ex.grade,
                    }
                    for ex in saved_exercises
                ],
                "count": len(saved_exercises),
            }
        except Exception as e:
            logger.error(f"习题生成失败: {e}")
            yield {"type": "error", "message": f"AI 服务暂时不可用: {str(e)}"}

    async def grade_answers(
        self,
        user_id: str,
        answers: list[dict],
        batch_id: str,
    ) -> dict:
        """批改作答 — 基于 batch_id 获取习题并批改"""
        # 获取批次中的题目
        stmt = select(ExerciseAttempt).where(
            ExerciseAttempt.batch_id == batch_id,
            ExerciseAttempt.user_id == user_id,
        )
        result = await self.db.execute(stmt)

        # 获取题目信息
        exercise_ids = [a["exercise_id"] for a in answers]
        stmt = select(Exercise).where(Exercise.id.in_(exercise_ids))
        result = await self.db.execute(stmt)
        exercises = {ex.id: ex for ex in result.scalars().all()}

        # 准备批改数据
        answers_data = []
        for ans in answers:
            ex = exercises.get(ans["exercise_id"])
            if ex:
                answers_data.append({
                    "exercise_id": ans["exercise_id"],
                    "user_answer": ans["user_answer"],
                    "correct_answer": ex.answer,
                    "question_type": ex.question_type,
                    "question": ex.question,
                    "analysis": ex.analysis or "",
                })

        # 客观题本地判断，主观题调 LLM
        results = []
        llm_answers = []

        for item in answers_data:
            if item["question_type"] in ("choice", "fill"):
                is_correct = item["user_answer"].strip() == item["correct_answer"].strip()
                results.append({
                    "exercise_id": item["exercise_id"],
                    "is_correct": is_correct,
                    "score": 20.0 if is_correct else 0.0,
                    "correct_answer": item["correct_answer"],
                    "analysis": item["analysis"],
                    "error_reason": None if is_correct else f"正确答案是: {item['correct_answer']}",
                    "related_knowledge": [],
                })
            else:
                llm_answers.append(item)

        if llm_answers:
            try:
                user_prompt = GRADING_USER_TEMPLATE.format(
                    answers_json=json.dumps(llm_answers, ensure_ascii=False)
                )
                messages = [
                    {"role": "system", "content": GRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
                llm_response = await llm_client.chat(messages)
                llm_results = json.loads(
                    llm_response.strip().removeprefix("```json").removesuffix("```").strip()
                )
                results.extend(llm_results)
            except Exception as e:
                logger.error(f"LLM 批改失败: {e}")
                for item in llm_answers:
                    results.append({
                        "exercise_id": item["exercise_id"],
                        "is_correct": None,
                        "score": 0,
                        "correct_answer": item["correct_answer"],
                        "analysis": item["analysis"],
                        "error_reason": "AI 批改暂不可用",
                        "related_knowledge": [],
                    })

        # 保存作答记录 + 更新批次
        total_correct = 0
        total_score = 0.0
        for ans in answers:
            ex_result = next(
                (r for r in results if r["exercise_id"] == ans["exercise_id"]), None
            )
            attempt = ExerciseAttempt(
                user_id=user_id,
                exercise_id=ans["exercise_id"],
                batch_id=batch_id,
                user_answer=ans["user_answer"],
                is_correct=ex_result["is_correct"] if ex_result else None,
                score=ex_result["score"] if ex_result else 0,
                graded_by="auto",
            )
            self.db.add(attempt)
            if ex_result and ex_result["is_correct"]:
                total_correct += 1
            if ex_result:
                total_score += ex_result["score"]
        await self.db.flush()

        # 更新批次状态
        batch = await self.db.get(ExerciseBatch, batch_id)
        if batch:
            batch.status = "done"
            batch.correct_count = total_correct
            batch.total_score = total_score
            batch.finished_at = func.now()
            self.db.add(batch)
            await self.db.flush()

        return {
            "total_score": round(total_score, 1),
            "correct_count": total_correct,
            "total_count": len(results),
            "results": results,
        }

    async def get_history(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """获取做题历史（按批次聚合，倒序）"""
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(ExerciseBatch)
            .where(ExerciseBatch.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页查询
        stmt = (
            select(ExerciseBatch)
            .where(ExerciseBatch.user_id == user_id)
            .order_by(ExerciseBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        batches = list(result.scalars().all())

        items = []
        for batch in batches:
            # 获取该批次下的所有 attempts
            attempt_stmt = (
                select(ExerciseAttempt)
                .where(ExerciseAttempt.batch_id == batch.id)
            )
            attempt_result = await self.db.execute(attempt_stmt)
            attempts = list(attempt_result.scalars().all())

            exercises_data = []
            for a in attempts:
                ex = await self.db.get(Exercise, a.exercise_id)
                exercises_data.append({
                    "exercise_id": a.exercise_id,
                    "question": ex.question if ex else "",
                    "question_type": ex.question_type if ex else "",
                    "user_answer": a.user_answer,
                    "is_correct": a.is_correct,
                    "score": a.score,
                })

            grade_result = None
            if batch.status == "done":
                grade_result = {
                    "total_score": batch.total_score,
                    "correct_count": batch.correct_count,
                    "total_count": batch.total_count,
                }

            items.append({
                "id": batch.id,
                "exercises": exercises_data,
                "grade_result": grade_result,
                "created_at": batch.created_at.isoformat() if batch.created_at else "",
            })

        return items, total

    async def get_batch_detail(self, batch_id: str, user_id: str) -> dict | None:
        """获取单个批次的详细作答"""
        batch = await self.db.get(ExerciseBatch, batch_id)
        if not batch or batch.user_id != user_id:
            return None

        attempt_stmt = (
            select(ExerciseAttempt)
            .where(ExerciseAttempt.batch_id == batch_id, ExerciseAttempt.user_id == user_id)
        )
        result = await self.db.execute(attempt_stmt)
        attempts = list(result.scalars().all())

        exercises_data = []
        for a in attempts:
            ex = await self.db.get(Exercise, a.exercise_id)
            exercises_data.append({
                "exercise_id": a.exercise_id,
                "question": ex.question if ex else "",
                "question_type": ex.question_type if ex else "",
                "options": ex.options,
                "user_answer": a.user_answer,
                "correct_answer": ex.answer if ex else "",
                "analysis": ex.analysis if ex else "",
                "is_correct": a.is_correct,
                "score": a.score,
                "knowledge_points": ex.knowledge_points if ex else [],
            })

        grade_result = None
        if batch.status == "done":
            grade_result = {
                "total_score": batch.total_score,
                "correct_count": batch.correct_count,
                "total_count": batch.total_count,
            }

        return {
            "id": batch.id,
            "exercises": exercises_data,
            "grade_result": grade_result,
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
        }

    async def delete_batch(self, batch_id: str, user_id: str) -> bool:
        """删除批次及其所有作答记录"""
        batch = await self.db.get(ExerciseBatch, batch_id)
        if not batch or batch.user_id != user_id:
            return False

        # 删除关联的 attempts
        del_stmt = delete(ExerciseAttempt).where(ExerciseAttempt.batch_id == batch_id)
        await self.db.execute(del_stmt)

        await self.db.delete(batch)
        await self.db.flush()
        return True

    @staticmethod
    def _parse_exercises_json(text: str) -> list[dict]:
        """从 LLM 返回文本中提取习题 JSON 数组"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "exercises" in data:
                return data["exercises"]
            return []
        except json.JSONDecodeError:
            logger.warning(f"无法解析 LLM 返回的习题 JSON: {text[:200]}")
            return []
