"""
习题服务层 (PBI_08, PBI_09, PBI_10)

负责:
- SSE 流式生成习题（调用 LLM）
- 习题批改（调用 LLM）
- 做题历史与批次管理
"""

import json
import re
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

# 选项前缀正则：匹配 "A.", "A.", "A)", "(A)" 等
_OPTION_PREFIX_RE = re.compile(r'^[A-D][.)]\s*')


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

        # 3. 解析习题 JSON（raw_decode 自动截断 LLM 追加的多余文本）
        exercises_data = []
        try:
            json_str = extract_json(full_text)
            if json_str:
                exercises_data = json.loads(json_str)
            else:
                # 回退：用 raw_decode 从原始响应中截取有效 JSON
                decoder = json.JSONDecoder()
                stripped = full_text.strip()
                for marker in ["[", "{"]:
                    idx = stripped.find(marker)
                    if idx == -1:
                        continue
                    try:
                        exercises_data, _ = decoder.raw_decode(stripped, idx)
                        break
                    except json.JSONDecodeError:
                        continue
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

            # 清理选择题选项：去除 LLM 可能添加的 "A." / "A)" 等前缀
            raw_options = ex.get("options")
            cleaned_options = None
            if raw_options and question_type == "choice":
                cleaned_options = [_OPTION_PREFIX_RE.sub('', opt) for opt in raw_options]

            exercise_dict = {
                "id": str(uuid.uuid4()),
                "question": ex.get("question", ""),
                "question_type": question_type,
                "options": cleaned_options,
                "answer": ex.get("answer"),
                "analysis": ex.get("analysis"),
                "difficulty": ex.get("difficulty", difficulty),
                "knowledge_points": ex.get("knowledge_points", knowledge_points),
            }

            # 持久化到数据库
            exercise = Exercise(
                id=exercise_dict["id"],
                user_id=user_id,
                batch_id=batch_id,
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

        # 同步更新学习档案
        await self._sync_learning_profile(user_id)

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
        获取用户的做题历史（按批次聚合，按时间倒序）。

        返回: (batches, total_batches)
        """
        # 查询用户所有习题，在 Python 中按 batch_id 分组
        # 避免使用 array_agg（MySQL 8.0 兼容性问题）
        stmt = (
            select(Exercise)
            .where(Exercise.user_id == user_id)
            .order_by(desc(Exercise.created_at))
        )
        result = await self.db.execute(stmt)
        all_exercises = result.scalars().all()

        if not all_exercises:
            return [], 0

        # 按 batch_id 分组（旧数据无 batch_id 时用 exercise id 兜底）
        batch_groups: dict[str, list[Exercise]] = {}
        for ex in all_exercises:
            key = ex.batch_id or ex.id
            batch_groups.setdefault(key, []).append(ex)

        # 按每组最新时间排序
        sorted_batches = sorted(
            batch_groups.items(),
            key=lambda item: max(ex.created_at for ex in item[1]),
            reverse=True,
        )

        total = len(sorted_batches)

        # 分页
        paged = sorted_batches[(page - 1) * page_size : page * page_size]

        # 收集所有 exercise_ids 用于批量查询作答记录
        all_ids = [ex.id for _, exercises in paged for ex in exercises]
        attempts_by_exercise: dict[str, ExerciseAttempt] = {}
        if all_ids:
            attempts_stmt = select(ExerciseAttempt).where(
                ExerciseAttempt.exercise_id.in_(all_ids)
            )
            attempts_result = await self.db.execute(attempts_stmt)
            for a in attempts_result.scalars().all():
                attempts_by_exercise[a.exercise_id] = a

        # 组装批次结果
        batches = []
        for batch_key, exercises in paged:
            correct_count = sum(
                1 for ex in exercises
                if attempts_by_exercise.get(ex.id) and attempts_by_exercise[ex.id].is_correct
            )
            graded_count = sum(1 for ex in exercises if ex.id in attempts_by_exercise)

            # 全部知识点（卡片展示用）
            kp_set: set[str] = set()
            # 错题知识点（薄弱知识点汇总用）
            weak_kp_set: set[str] = set()
            for ex in exercises:
                if ex.knowledge_points:
                    for kp in ex.knowledge_points:
                        kp_str = kp if isinstance(kp, str) else str(kp)
                        kp_set.add(kp_str)
                        # 只统计答错的知识点
                        att = attempts_by_exercise.get(ex.id)
                        if att and att.is_correct is False:
                            weak_kp_set.add(kp_str)

            batches.append({
                "batch_id": batch_key,
                "subject": exercises[0].subject,
                "grade": exercises[0].grade,
                "difficulty": exercises[0].difficulty,
                "exercise_count": len(exercises),
                "graded_count": graded_count,
                "correct_count": correct_count,
                "knowledge_points": sorted(kp_set),
                "weak_knowledge_points": sorted(weak_kp_set),
                "created_at": max(ex.created_at for ex in exercises).isoformat(),
            })

        return batches, total

    async def get_batch_detail(self, user_id: str, batch_id: str) -> dict | None:
        """
        获取单次练习详情（包含习题和作答记录）。

        参数:
            user_id: 用户 ID
            batch_id: 批次 ID
        """
        # 按 batch_id 精确查询
        stmt = (
            select(Exercise)
            .where(
                Exercise.user_id == user_id,
                Exercise.batch_id == batch_id,
            )
            .order_by(Exercise.created_at)
        )
        result = await self.db.execute(stmt)
        exercises = result.scalars().all()

        # 兼容旧数据：如果没有 batch_id 匹配，回退到按 id 查询
        if not exercises:
            stmt = (
                select(Exercise)
                .where(
                    Exercise.user_id == user_id,
                    Exercise.id == batch_id,
                )
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
        total_score = 0.0
        correct_count = 0
        for ex in exercises:
            attempt = attempts_map.get(ex.id)
            if attempt and attempt.is_correct:
                correct_count += 1
                total_score += float(attempt.score or 0)
            elif attempt:
                total_score += float(attempt.score or 0)
            exercises_data.append({
                "id": ex.id,
                "subject": ex.subject,
                "grade": ex.grade,
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

        has_attempts = len(attempts_map) > 0
        grade_result = None
        if has_attempts:
            grade_result = {
                "total_score": total_score,
                "correct_count": correct_count,
                "total_count": len(exercises),
            }

        return {
            "batch_id": batch_id,
            "exercises": exercises_data,
            "grade_result": grade_result,
        }

    async def delete_batch(self, user_id: str, batch_id: str) -> bool:
        """
        删除一批练习记录。

        参数:
            user_id: 用户 ID
            batch_id: 批次 ID
        """
        # 1. 查出该批次的所有习题 ID
        id_stmt = select(Exercise.id).where(
            Exercise.user_id == user_id,
            Exercise.batch_id == batch_id,
        )
        id_result = await self.db.execute(id_stmt)
        exercise_ids = [row[0] for row in id_result.all()]

        # 兼容旧数据：batch_id 为空时，前端用 exercise.id 兜底
        if not exercise_ids:
            id_stmt = select(Exercise.id).where(
                Exercise.user_id == user_id,
                Exercise.id == batch_id,
            )
            id_result = await self.db.execute(id_stmt)
            exercise_ids = [row[0] for row in id_result.all()]

        if not exercise_ids:
            return False

        # 2. 先删关联的作答记录（避免外键约束阻止删除）
        del_attempts = delete(ExerciseAttempt).where(
            ExerciseAttempt.exercise_id.in_(exercise_ids)
        )
        await self.db.execute(del_attempts)

        # 3. 再删习题
        del_exercises = delete(Exercise).where(
            Exercise.id.in_(exercise_ids)
        )
        result = await self.db.execute(del_exercises)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(
                f"习题记录已删除 | user={user_id} | batch={batch_id} "
                f"| deleted_count={result.rowcount}"
            )
        return deleted

    # ================================================================
    # 学习档案同步
    # ================================================================

    async def _sync_learning_profile(self, user_id: str) -> None:
        """同步更新学习档案中的统计数据"""
        from app.models.user import LearningProfile
        from sqlalchemy import select as sa_select

        profile_stmt = sa_select(LearningProfile).where(LearningProfile.user_id == user_id)
        profile_result = await self.db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            return

        # 重新计算做题总数和正确率
        total_stmt = (
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id)
        )
        total = (await self.db.execute(total_stmt)).scalar() or 0

        correct_stmt = (
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.is_correct == True,
            )
        )
        correct = (await self.db.execute(correct_stmt)).scalar() or 0

        profile.total_exercises = total
        profile.correct_rate = round(correct / total, 2) if total > 0 else 0.0

        # 学习时长估算（每次答题约 2 分钟 = 120 秒）
        profile.total_study_time = (profile.total_study_time or 0) + 120

        # 更新薄弱知识点
        weak_kp_stmt = (
            select(Exercise.knowledge_points)
            .join(ExerciseAttempt, ExerciseAttempt.exercise_id == Exercise.id)
            .where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.is_correct == False,
            )
            .order_by(ExerciseAttempt.created_at.desc())
            .limit(50)
        )
        weak_kp_rows = (await self.db.execute(weak_kp_stmt)).scalars().all()
        kp_counter: dict[str, int] = {}
        for kp_list in weak_kp_rows:
            for kp in (kp_list or []):
                name = kp if isinstance(kp, str) else kp.get("name", str(kp))
                kp_counter[name] = kp_counter.get(name, 0) + 1
        profile.weak_points = sorted(kp_counter, key=kp_counter.get, reverse=True)[:10]

        await self.db.flush()
