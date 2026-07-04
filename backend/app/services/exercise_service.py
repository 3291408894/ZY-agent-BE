"""
习题服务层 (PBI_08, PBI_09, PBI_10)
"""

import json
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import delete, select
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
from app.models.exercise import Exercise, ExerciseAttempt


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
        """流式生成习题"""
        if question_types is None:
            question_types = ["choice"]

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

        # 生成唯一 batch_id
        import uuid
        batch_id = str(uuid.uuid4())

        yield {"type": "meta", "batch_id": batch_id}

        full_text = ""
        try:
            async for chunk in llm_client.chat_stream(messages):
                full_text += chunk
                yield {"type": "content", "chunk": chunk}

            # 解析 LLM 返回的 JSON 习题列表
            exercises_data = self._parse_exercises_json(full_text)
            saved_exercises = []

            for ex_data in exercises_data:
                exercise = Exercise(
                    user_id=user_id,
                    subject=subject,
                    grade=grade,
                    question_type=ex_data.get("question_type", "choice"),
                    question=ex_data.get("question", ""),
                    options=ex_data.get("options"),
                    answer=ex_data.get("answer", ""),
                    analysis=ex_data.get("analysis", ""),
                    difficulty=difficulty,
                    knowledge_points=ex_data.get("knowledge_points", knowledge_points),
                )
                self.db.add(exercise)
                saved_exercises.append(exercise)

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
                        "difficulty": ex.difficulty,
                        "knowledge_points": ex.knowledge_points,
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
        batch_id: str | None = None,
    ) -> dict:
        """批改作答"""
        # 获取题目信息
        exercise_ids = [a["exercise_id"] for a in answers]
        stmt = select(Exercise).where(Exercise.id.in_(exercise_ids))
        result = await self.db.execute(stmt)
        exercises = {ex.id: ex for ex in result.scalars().all()}

        # 准备批改数据
        answers_data = []
        for ans in answers:
            ex = exercises.get(ans["exercise_id"])
            answers_data.append({
                "exercise_id": ans["exercise_id"],
                "user_answer": ans["user_answer"],
                "correct_answer": ex.answer if ex else "",
                "question_type": ex.question_type if ex else "choice",
                "question": ex.question if ex else "",
                "analysis": ex.analysis if ex else "",
            })

        # 对于客观题（选择/填空），先本地判断
        results = []
        llm_answers = []

        for item in answers_data:
            if item["question_type"] in ("choice", "fill"):
                # 本地判分
                is_correct = item["user_answer"].strip() == item["correct_answer"].strip()
                results.append({
                    "exercise_id": item["exercise_id"],
                    "is_correct": is_correct,
                    "score": 100.0 if is_correct else 0.0,
                    "correct_answer": item["correct_answer"],
                    "analysis": item["analysis"],
                    "error_reason": None if is_correct else f"正确答案是: {item['correct_answer']}",
                    "related_knowledge": [],
                })
            else:
                llm_answers.append(item)

        # 主观题调用 LLM 批改
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
                # 降级：主观题标记为待批改
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

        # 保存作答记录
        for ans in answers:
            ex_result = next(
                (r for r in results if r["exercise_id"] == ans["exercise_id"]), None
            )
            attempt = ExerciseAttempt(
                user_id=user_id,
                exercise_id=ans["exercise_id"],
                user_answer=ans["user_answer"],
                is_correct=ex_result["is_correct"] if ex_result else None,
                score=ex_result["score"] if ex_result else 0,
                graded_by="auto",
            )
            self.db.add(attempt)
        await self.db.flush()

        # 汇总
        total_score = sum(r["score"] for r in results)
        correct_count = sum(1 for r in results if r["is_correct"])
        return {
            "total_score": total_score,
            "correct_count": correct_count,
            "total_count": len(results),
            "results": results,
        }

    async def get_history(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """获取做题历史（按批次聚合）"""
        # 获取所有 attempt，按时间倒序，按 exercise 聚合
        stmt = (
            select(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id)
            .order_by(ExerciseAttempt.created_at.desc())
        )
        result = await self.db.execute(stmt)
        all_attempts = list(result.scalars().all())

        # 按 created_at 分组为批次（同一分钟内的算一批）
        batches = {}
        for a in all_attempts:
            batch_key = a.created_at.strftime("%Y%m%d%H%M") if a.created_at else "unknown"
            if batch_key not in batches:
                batches[batch_key] = {"attempts": [], "time": a.created_at}
            batches[batch_key]["attempts"].append(a)

        batch_list = list(batches.values())
        total = len(batch_list)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_batches = batch_list[start:end]

        items = []
        for batch in page_batches:
            attempts = batch["attempts"]
            items.append({
                "batch_time": batch["time"].isoformat() if batch["time"] else "",
                "count": len(attempts),
                "correct": sum(1 for a in attempts if a.is_correct),
                "exercises": [
                    {"exercise_id": a.exercise_id, "score": a.score, "is_correct": a.is_correct}
                    for a in attempts
                ],
            })

        return items, total

    async def get_batch_detail(self, batch_time: str, user_id: str) -> list[dict]:
        """获取某个批次的详细作答"""
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(batch_time)
            batch_key = dt.strftime("%Y%m%d%H%M")
        except ValueError:
            return []

        stmt = (
            select(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id)
            .order_by(ExerciseAttempt.created_at.desc())
        )
        result = await self.db.execute(stmt)
        all_attempts = list(result.scalars().all())

        batch_attempts = [
            a for a in all_attempts
            if a.created_at and a.created_at.strftime("%Y%m%d%H%M") == batch_key
        ]

        details = []
        for a in batch_attempts:
            ex = await self.db.get(Exercise, a.exercise_id)
            details.append({
                "attempt_id": a.id,
                "exercise_id": a.exercise_id,
                "question": ex.question if ex else "",
                "question_type": ex.question_type if ex else "",
                "user_answer": a.user_answer,
                "correct_answer": ex.answer if ex else "",
                "analysis": ex.analysis if ex else "",
                "is_correct": a.is_correct,
                "score": a.score,
            })

        return details

    async def delete_batch(self, batch_time: str, user_id: str) -> int:
        """删除某个批次的作答记录"""
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(batch_time)
            batch_key = dt.strftime("%Y%m%d%H%M")
        except ValueError:
            return 0

        stmt = (
            select(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id)
            .order_by(ExerciseAttempt.created_at.desc())
        )
        result = await self.db.execute(stmt)
        all_attempts = list(result.scalars().all())

        deleted = 0
        for a in all_attempts:
            if a.created_at and a.created_at.strftime("%Y%m%d%H%M") == batch_key:
                await self.db.delete(a)
                deleted += 1

        await self.db.flush()
        return deleted

    @staticmethod
    def _parse_exercises_json(text: str) -> list[dict]:
        """从 LLM 返回文本中提取习题 JSON 数组"""
        # 去除可能的 markdown 代码块包裹
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
