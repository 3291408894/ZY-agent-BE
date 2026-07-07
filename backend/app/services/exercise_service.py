"""
习题服务层 (PBI_08, PBI_09, PBI_10)

负责:
- SSE 流式生成习题（调用 LLM）
- 习题批改（调用 LLM）
- 做题历史与批次管理
"""

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import desc, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.exercise_gen import EXERCISE_GEN_SYSTEM_PROMPT, EXERCISE_GEN_USER_TEMPLATE
from app.core.utils import sse_json, extract_json
from app.models.exercise import Exercise, ExerciseAttempt


class ExerciseService:
    """习题业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # SSE 流式生成习题
    # ================================================================

    async def generate_exercises_stream(
        self,
        user_id: str,
        subject: str,
        grade: str,
        knowledge_points: list[str],
        difficulty: str = "medium",
        question_types: list[str] | None = None,
        count: int = 5,
    ) -> AsyncIterator[str]:
        """
        SSE 流式生成习题。

        每个 yield 返回一行 SSE 格式的 JSON 字符串（不含 'data: ' 前缀）。

        SSE 事件类型:
        - progress: 生成进度
        - exercise: 单道习题
        - done: 生成完成（含 batch_id）
        - error: 错误信息
        """
        if question_types is None:
            question_types = ["choice"]

        # 1. 构建 Prompt
        knowledge_str = "、".join(knowledge_points)
        types_str = "、".join(question_types)
        user_prompt = EXERCISE_GEN_USER_TEMPLATE.format(
            count=count,
            subject=subject,
            grade=grade,
            knowledge_points=knowledge_str,
            difficulty=difficulty,
            question_types=types_str,
        )
        messages = [
            {"role": "system", "content": EXERCISE_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 2. 流式调用 LLM
        full_text = ""
        try:
            # 先用非流式调用获取完整习题（因为 SS 习题需要一次解析整个 JSON 数组）
            response = await llm_client.chat(messages, temperature=0.7, max_tokens=4096)
            full_text = response
        except Exception as e:
            logger.error(f"LLM 习题生成失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": f"AI 服务调用失败: {str(e)}"})
            return

        # 3. 解析习题 JSON
        exercises_data = []
        try:
            json_str = extract_json(full_text)
            if json_str:
                exercises_data = json.loads(json_str)
            else:
                # 尝试直接解析整个响应
                exercises_data = json.loads(full_text.strip())
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM 返回的习题 JSON 解析失败 | user={user_id} | error={e}")
            yield sse_json({"type": "error", "message": "AI 生成的习题格式异常，请重试"})
            return

        if not isinstance(exercises_data, list) or len(exercises_data) == 0:
            yield sse_json({"type": "error", "message": "AI 未能生成有效习题，请调整参数后重试"})
            return

        # 4. 生成 batch_id
        batch_id = str(uuid.uuid4())

        # 5. 逐道返回习题 (SSE stream with progress)
        total = len(exercises_data)
        for i, ex in enumerate(exercises_data):
            # 发送进度
            yield sse_json({
                "type": "progress",
                "generated": i + 1,
                "total": total,
            })

            # 构造习题对象
            question_type = ex.get("question_type", "choice")
            exercise_dict = {
                "id": str(uuid.uuid4()),
                "question": ex.get("question", ""),
                "question_type": question_type,
                "options": ex.get("options"),
                "answer": ex.get("answer"),
                "analysis": ex.get("analysis"),
                "difficulty": ex.get("difficulty", difficulty),
                "knowledge_points": ex.get("knowledge_points", knowledge_points),
            }

            # 持久化到数据库
            exercise = Exercise(
                id=exercise_dict["id"],
                user_id=user_id,
                subject=subject,
                grade=grade,
                question_type=question_type,
                question=exercise_dict["question"],
                options=exercise_dict["options"],
                answer=exercise_dict["answer"],
                analysis=exercise_dict.get("analysis"),
                difficulty=exercise_dict.get("difficulty", difficulty),
                knowledge_points=exercise_dict.get("knowledge_points", knowledge_points),
            )
            self.db.add(exercise)

            # 发送习题（不含答案和解析，前端做题模式）
            yield sse_json({
                "type": "exercise",
                "exercise": {
                    "id": exercise_dict["id"],
                    "question": exercise_dict["question"],
                    "question_type": exercise_dict["question_type"],
                    "options": exercise_dict["options"],
                    "difficulty": exercise_dict.get("difficulty", difficulty),
                    "knowledge_points": exercise_dict.get("knowledge_points", knowledge_points),
                    # 做题模式下不发送 answer 和 analysis
                },
            })

        await self.db.flush()
        logger.info(
            f"习题已保存 | batch_id={batch_id} | user={user_id} "
            f"| subject={subject} | count={total}"
        )

        # 6. 完成事件
        yield sse_json({
            "type": "done",
            "batch_id": batch_id,
        })

    # ================================================================
    # 习题批改
    # ================================================================

    async def grade_answers(
        self,
        user_id: str,
        batch_id: str,
        answers: list[dict],
    ) -> dict:
        """
        批改学生的作答。

        参数:
            user_id: 用户 ID
            batch_id: 批次 ID
            answers: [{"exercise_id": "...", "user_answer": "..."}]

        返回:
            {"total_score": float, "correct_count": int, "total_count": int, "results": [...]}
        """
        results = []
        total_score = 0.0
        correct_count = 0

        for answer_item in answers:
            exercise_id = answer_item["exercise_id"]
            user_answer = answer_item["user_answer"]

            # 查找习题
            stmt = select(Exercise).where(
                Exercise.id == exercise_id,
                Exercise.user_id == user_id,
            )
            result = await self.db.execute(stmt)
            exercise = result.scalar_one_or_none()

            if not exercise:
                results.append({
                    "exercise_id": exercise_id,
                    "is_correct": False,
                    "score": 0,
                    "correct_answer": "",
                    "analysis": "",
                    "error_reason": "习题不存在",
                    "related_knowledge": [],
                })
                continue

            # 使用 LLM 批改
            is_correct, score, error_reason = await self._grade_single(
                exercise.question,
                exercise.answer or "",
                user_answer,
                exercise.question_type,
            )

            total_score += score
            if is_correct:
                correct_count += 1

            # 保存作答记录
            attempt = ExerciseAttempt(
                user_id=user_id,
                exercise_id=exercise_id,
                user_answer=user_answer,
                is_correct=is_correct,
                score=score,
                graded_by="auto",
            )
            self.db.add(attempt)

            results.append({
                "exercise_id": exercise_id,
                "is_correct": is_correct,
                "score": score,
                "correct_answer": exercise.answer or "",
                "analysis": exercise.analysis or "",
                "error_reason": error_reason,
                "related_knowledge": exercise.knowledge_points or [],
            })

        await self.db.flush()
        logger.info(
            f"批改完成 | user={user_id} | batch={batch_id} "
            f"| correct={correct_count}/{len(answers)} | score={total_score}"
        )

        return {
            "total_score": total_score,
            "correct_count": correct_count,
            "total_count": len(answers),
            "results": results,
        }

    async def _grade_single(
        self,
        question: str,
        correct_answer: str,
        user_answer: str,
        question_type: str,
    ) -> tuple[bool, float, str | None]:
        """
        使用 LLM 批改单道习题。

        返回: (is_correct, score, error_reason)
        """
        prompt = f"""你是一位K12学科教师，请批改学生的作答。

题目：{question}
题型：{question_type}
标准答案：{correct_answer}
学生作答：{user_answer}

请判断学生的作答是否正确，并给出评分（0或满分1分）。
对于简答题和分析题，如果学生的回答与标准答案的核心要点一致，可以给满分。

请以 JSON 格式输出：
{{"is_correct": true/false, "score": 0-1之间的浮点数, "error_reason": "错误原因（正确则为null）"}}

只输出 JSON，不要包含其他文字。"""

        try:
            response = await llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            json_str = extract_json(response)
            if json_str:
                data = json.loads(json_str)
            else:
                data = json.loads(response.strip())

            is_correct = data.get("is_correct", False)
            score = float(data.get("score", 0))
            error_reason = data.get("error_reason")

            return is_correct, score, error_reason

        except Exception as e:
            logger.warning(f"LLM 批改失败，回退到简单匹配 | error={e}")
            # 回退：简单字符串匹配
            user_clean = user_answer.strip().lower()
            correct_clean = correct_answer.strip().lower()
            is_correct = user_clean == correct_clean
            score = 1.0 if is_correct else 0.0
            error_reason = None if is_correct else "与标准答案不符"
            return is_correct, score, error_reason

    # ================================================================
    # 做题历史
    # ================================================================

    async def get_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        获取用户的做题历史（按时间倒序，按批次聚合）。

        返回: (items, total)
        """
        # 按创建时间分组（同一批次 = 同一秒内创建的习题）
        # 简化处理：直接查询用户的所有习题，按时间倒序
        count_stmt = (
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.user_id == user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Exercise)
            .where(Exercise.user_id == user_id)
            .order_by(desc(Exercise.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        exercises = result.scalars().all()

        items = []
        for ex in exercises:
            items.append({
                "id": ex.id,
                "subject": ex.subject,
                "grade": ex.grade,
                "question_type": ex.question_type,
                "question": ex.question,
                "difficulty": ex.difficulty,
                "knowledge_points": ex.knowledge_points,
                "created_at": ex.created_at.isoformat() if ex.created_at else None,
            })

        return items, total

    async def get_batch_detail(self, user_id: str, batch_id: str) -> dict | None:
        """
        获取单次练习详情（包含习题和作答记录）。

        参数:
            user_id: 用户 ID
            batch_id: 批次 ID（这里简化为查询该用户最近生成的一批习题）
        """
        # 查询该用户的所有习题，按时间倒序
        stmt = (
            select(Exercise)
            .where(Exercise.user_id == user_id)
            .order_by(desc(Exercise.created_at))
            .limit(100)
        )
        result = await self.db.execute(stmt)
        exercises = result.scalars().all()

        if not exercises:
            return None

        # 查找对应的作答记录
        exercise_ids = [ex.id for ex in exercises]
        attempts_stmt = (
            select(ExerciseAttempt)
            .where(ExerciseAttempt.exercise_id.in_(exercise_ids))
            .order_by(ExerciseAttempt.created_at)
        )
        attempts_result = await self.db.execute(attempts_stmt)
        attempts = attempts_result.scalars().all()
        attempts_map = {a.exercise_id: a for a in attempts}

        exercises_data = []
        for ex in exercises:
            attempt = attempts_map.get(ex.id)
            exercises_data.append({
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
                "created_at": ex.created_at.isoformat() if ex.created_at else None,
            })

        return {
            "batch_id": batch_id,
            "exercises": exercises_data,
        }

    async def delete_batch(self, user_id: str, batch_id: str) -> bool:
        """
        删除一批练习记录。

        参数:
            user_id: 用户 ID
            batch_id: 批次 ID
        """
        # 安全校验：只能删除自己的
        stmt = delete(Exercise).where(
            Exercise.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"习题记录已删除 | user={user_id} | deleted_count={result.rowcount}")
        return deleted
