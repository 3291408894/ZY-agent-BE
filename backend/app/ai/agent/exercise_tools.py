"""
习题模块 Agent 工具注册 (PBI_08, PBI_10)

提供 exercise_generate 和 exercise_grade 两个工具，
Agent 编排器可根据用户意图自动调用。
"""

from loguru import logger

from app.ai.agent.tools import AgentTool, tool_registry
from app.core.database import AsyncSessionLocal
from app.schemas.exercise import Difficulty, GenerateExerciseReq, QuestionType


# ── exercise_generate 工具处理函数 ──────────────────────────────


async def _exercise_generate_handler(
    subject: str,
    grade: str,
    knowledge_points: list[str],
    difficulty: str = "medium",
    question_types: list[str] | None = None,
    count: int = 5,
    user_id: str = "",
) -> dict:
    """
    生成习题 — Agent 工具调用入口

    参数：
        subject: 学科（语文/数学/英语/物理/化学/生物/历史/地理/政治）
        grade: 年级（如 七年级、八年级）
        knowledge_points: 知识点列表
        difficulty: easy/medium/hard
        question_types: choice/fill/short_answer/calculation/analysis
        count: 生成数量 (1-50)
        user_id: 当前用户ID（由Agent上下文注入）

    返回：
        {batch_id, exercises: [{id, question, question_type, answer, analysis}]}
    """
    if question_types is None:
        question_types = ["choice"]

    from app.services.exercise_service import ExerciseService

    async with AsyncSessionLocal() as db:
        try:
            req = GenerateExerciseReq(
                subject=subject,
                grade=grade,
                knowledge_points=knowledge_points,
                difficulty=Difficulty(difficulty),
                question_types=[
                    QuestionType(qt) for qt in question_types
                ],
                count=count,
                mode="review",  # Agent 调用时返回完整答案
            )
            service = ExerciseService(db)
            batch_id, exercises = await service.generate(
                user_id=user_id, req=req
            )
            await db.commit()

            result = {
                "batch_id": batch_id,
                "exercises": [
                    {
                        "id": ex.id,
                        "question": ex.question,
                        "question_type": ex.question_type,
                        "options": ex.options,
                        "answer": ex.answer,
                        "analysis": ex.analysis,
                        "difficulty": ex.difficulty,
                        "knowledge_points": ex.knowledge_points,
                    }
                    for ex in exercises
                ],
            }
            logger.info(
                f"[Agent工具] exercise_generate 完成 | batch_id={batch_id}"
            )
            return result
        except Exception as e:
            logger.error(f"[Agent工具] exercise_generate 失败: {e}")
            raise


# ── exercise_grade 工具处理函数 ──────────────────────────────────


async def _exercise_grade_handler(
    answers: list[dict],
    user_id: str = "",
) -> dict:
    """
    批改习题 — Agent 工具调用入口

    参数：
        answers: [{exercise_id, user_answer}, ...]
        user_id: 当前用户ID（由Agent上下文注入）

    返回：
        {total_score, correct_count, total_count, results: [{...}]}
    """
    from app.schemas.exercise import AnswerItem, GradeReq
    from app.services.exercise_service import ExerciseService

    async with AsyncSessionLocal() as db:
        try:
            answer_items = [
                AnswerItem(
                    exercise_id=a["exercise_id"],
                    user_answer=a["user_answer"],
                )
                for a in answers
            ]
            req = GradeReq(answers=answer_items)
            service = ExerciseService(db)
            result = await service.grade(user_id=user_id, req=req)
            await db.commit()

            logger.info(
                f"[Agent工具] exercise_grade 完成 | "
                f"总分={result.total_score} | "
                f"正确={result.correct_count}/{result.total_count}"
            )
            return result.model_dump()
        except Exception as e:
            logger.error(f"[Agent工具] exercise_grade 失败: {e}")
            raise


# ── 注册到全局工具注册中心 ──────────────────────────────────────


def register_exercise_tools():
    """将习题模块工具注册到 Agent 工具注册中心（幂等）"""
    existing = tool_registry.get_tool_names()

    if "exercise_generate" not in existing:
        tool_registry.register(
            AgentTool(
                name="exercise_generate",
                description=(
                    "根据学科、年级、知识点和难度生成练习题。"
                    "支持5种题型：选择题(choice)、填空题(fill)、简答题(short_answer)、"
                    "计算题(calculation)、辨析题(analysis)。"
                    "难度分为 easy（基础）、medium（中等）、hard（拔高）。"
                    "适用于：学生说'帮我出几道题'、'我要练习XX知识点'等场景。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "学科，如：语文、数学、英语、物理、化学、生物、历史、地理、政治",
                        },
                        "grade": {
                            "type": "string",
                            "description": "年级，如：七年级、八年级、九年级",
                        },
                        "knowledge_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "考查的知识点列表",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard"],
                            "description": "难度等级",
                        },
                        "question_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "choice",
                                    "fill",
                                    "short_answer",
                                    "calculation",
                                    "analysis",
                                ],
                            },
                            "description": "题型列表",
                        },
                        "count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "description": "生成数量",
                        },
                        "user_id": {
                            "type": "string",
                            "description": "当前用户ID（系统自动注入）",
                        },
                    },
                    "required": ["subject", "grade", "knowledge_points"],
                },
                handler=_exercise_generate_handler,
            )
        )
        logger.info("[ToolRegistry] 注册工具: exercise_generate")

    if "exercise_grade" not in existing:
        tool_registry.register(
            AgentTool(
                name="exercise_grade",
                description=(
                    "批改学生的习题作答，给出评分、正确性判断和纠错建议。"
                    "支持客观题（选择题/填空题，零分或满分）和主观题"
                    "（简答题/计算题/辨析题，按要点给分）。"
                    "适用于：学生说'帮我批改'、'对答案'等场景。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "exercise_id": {
                                        "type": "string",
                                        "description": "习题ID",
                                    },
                                    "user_answer": {
                                        "type": "string",
                                        "description": "学生作答内容",
                                    },
                                },
                                "required": [
                                    "exercise_id",
                                    "user_answer",
                                ],
                            },
                            "description": "作答列表",
                        },
                        "user_id": {
                            "type": "string",
                            "description": "当前用户ID（系统自动注入）",
                        },
                    },
                    "required": ["answers"],
                },
                handler=_exercise_grade_handler,
            )
        )
        logger.info("[ToolRegistry] 注册工具: exercise_grade")


# 模块导入时自动注册
register_exercise_tools()
