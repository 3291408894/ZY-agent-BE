"""
作业管理服务 (功能5) — 布置/提交/AI批改/统计
"""

import json
import asyncio
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm_client import LLMClient
from app.ai.prompts.assignment_grading import GRADING_SYSTEM_PROMPT, GRADING_USER_TEMPLATE
from app.core.utils import extract_json
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.classes import Class, ClassStudent
from app.models.user import User


class AssignmentService:
    """作业管理业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMClient()

    # ============================================================
    # 教师端 — 布置与管理
    # ============================================================

    async def create_assignment(
        self,
        teacher_id: str,
        class_id: str,
        title: str,
        subject: str,
        content: dict,
        due_date: datetime,
        description: str | None = None,
        total_score: int | None = None,
        allow_late_submission: bool = False,
    ) -> Assignment | None:
        """布置作业，校验班级归属"""
        # 验证班级归属
        cls = await self.db.get(Class, class_id)
        if not cls or cls.teacher_id != teacher_id:
            return None

        assignment = Assignment(
            class_id=class_id,
            teacher_id=teacher_id,
            title=title,
            description=description,
            subject=subject,
            content=content,
            total_score=total_score,
            due_date=due_date,
            allow_late_submission=allow_late_submission,
        )
        self.db.add(assignment)
        await self.db.flush()
        now = datetime.utcnow()
        return {
            "id": assignment.id,
            "class_id": assignment.class_id,
            "title": assignment.title,
            "subject": assignment.subject,
            "total_score": assignment.total_score,
            "due_date": assignment.due_date,
            "status": assignment.status,
            "created_at": now,
        }

    async def update_assignment(
        self, assignment_id: str, teacher_id: str, **kwargs
    ) -> Assignment | None:
        """修改作业（仅截止时间/说明等）"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(assignment, key):
                setattr(assignment, key, value)
        return assignment

    async def get_teacher_assignments(
        self,
        teacher_id: str,
        page: int = 1,
        page_size: int = 20,
        class_id: str | None = None,
        status: str | None = None,
        subject: str | None = None,
    ) -> tuple[list[dict], int]:
        """获取教师布置的作业列表"""
        conditions = [Assignment.teacher_id == teacher_id]
        if class_id:
            conditions.append(Assignment.class_id == class_id)
        if status:
            conditions.append(Assignment.status == status)
        if subject:
            conditions.append(Assignment.subject == subject)

        count_stmt = (
            select(func.count()).select_from(Assignment).where(and_(*conditions))
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Assignment)
            .where(and_(*conditions))
            .options(selectinload(Assignment.class_))
            .order_by(Assignment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        assignments = result.unique().scalars().all()

        items = []
        for a in assignments:
            items.append({
                "id": a.id,
                "class_id": a.class_id,
                "class_name": a.class_.name if a.class_ else "",
                "title": a.title,
                "subject": a.subject,
                "total_score": a.total_score,
                "due_date": a.due_date,
                "allow_late_submission": a.allow_late_submission,
                "submission_count": a.submission_count,
                "graded_count": a.graded_count,
                "status": a.status,
                "created_at": a.created_at,
            })
        return items, total

    async def get_assignment_detail(self, assignment_id: str) -> dict | None:
        """获取作业详情"""
        stmt = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .options(selectinload(Assignment.class_))
        )
        result = await self.db.execute(stmt)
        a = result.unique().scalar_one_or_none()
        if not a:
            return None

        return {
            "id": a.id,
            "class_id": a.class_id,
            "class_name": a.class_.name if a.class_ else "",
            "teacher_id": a.teacher_id,
            "title": a.title,
            "description": a.description,
            "subject": a.subject,
            "content": a.content,
            "total_score": a.total_score,
            "due_date": a.due_date,
            "allow_late_submission": a.allow_late_submission,
            "submission_count": a.submission_count,
            "graded_count": a.graded_count,
            "status": a.status,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }

    async def delete_assignment(self, assignment_id: str, teacher_id: str) -> bool:
        """删除作业（无提交时才能删除）"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return False
        if assignment.submission_count > 0:
            return False  # 有提交记录不可删除
        await self.db.delete(assignment)
        return True

    async def get_submissions(
        self,
        assignment_id: str,
        teacher_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict], int] | None:
        """获取提交列表，校验教师权限"""
        # 验证权限
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        conditions = [AssignmentSubmission.assignment_id == assignment_id]
        if status:
            conditions.append(AssignmentSubmission.status == status)

        count_stmt = (
            select(func.count())
            .select_from(AssignmentSubmission)
            .where(and_(*conditions))
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(AssignmentSubmission)
            .where(and_(*conditions))
            .options(selectinload(AssignmentSubmission.student))
            .order_by(AssignmentSubmission.submitted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        submissions = result.unique().scalars().all()

        items = []
        for s in submissions:
            items.append({
                "id": s.id,
                "assignment_id": s.assignment_id,
                "student_id": s.student_id,
                "student_name": s.student.nickname if s.student else "未知",
                "student_nickname": s.student.nickname if s.student else "未知",
                "score": s.score,
                "status": s.status,
                "submitted_at": s.submitted_at,
                "graded_at": s.graded_at,
            })
        return items, total

    async def get_submission_detail(
        self, assignment_id: str, submission_id: str, teacher_id: str
    ) -> dict | None:
        """获取单份提交详情"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        stmt = (
            select(AssignmentSubmission)
            .where(
                and_(
                    AssignmentSubmission.id == submission_id,
                    AssignmentSubmission.assignment_id == assignment_id,
                )
            )
            .options(selectinload(AssignmentSubmission.student))
        )
        result = await self.db.execute(stmt)
        s = result.unique().scalar_one_or_none()
        if not s:
            return None

        return {
            "id": s.id,
            "assignment_id": s.assignment_id,
            "student_id": s.student_id,
            "student_name": s.student.nickname if s.student else "未知",
            "content": s.content,
            "attachments": s.attachments,
            "score": s.score,
            "ai_feedback": s.ai_feedback,
            "teacher_feedback": s.teacher_feedback,
            "teacher_id": s.teacher_id,
            "status": s.status,
            "submitted_at": s.submitted_at,
            "graded_at": s.graded_at,
        }

    # ============================================================
    # AI 批改
    # ============================================================

    @staticmethod
    def _normalize_answer(ans: str) -> str:
        """归一化答案：去除空格、点号、括号，转大写，取首字母"""
        import re
        a = ans.strip().upper()
        # 去除常见的答案前缀标记: A.  A)  (A)  A、
        a = re.sub(r'^[\(（]?([A-Z])[\)）]?[.、:：]?\s*$', r'\1', a)
        return a.strip()

    async def _grade_objective_question(
        self, question: dict, student_answer: str
    ) -> dict:
        """客观题自动判分（归一化后比对）"""
        correct_answer = self._normalize_answer(question.get("answer", ""))
        student_ans = self._normalize_answer(student_answer)
        max_s = question.get("score", 0)

        # 如果答案看起来是单字母选择，只比较首字母
        if len(correct_answer) == 1 and len(student_ans) >= 1:
            is_correct = student_ans[0] == correct_answer
        else:
            is_correct = student_ans == correct_answer

        return {
            "score": max_s if is_correct else 0,
            "overall_comment": "回答正确" if is_correct else f"回答错误，正确答案是 {correct_answer}",
            "step_feedback": [],
            "error_analysis": None if is_correct else f"选择了 {student_ans or '(空)'}，正确答案应为 {correct_answer}",
            "suggested_score": max_s if is_correct else 0,
        }

    async def _grade_subjective_question(
        self, question: dict, student_answer: str, question_number: int
    ) -> dict:
        """主观题调用 LLM 批改"""
        question_type = question.get("type", "subjective")
        score = question.get("score", 0)
        stem = question.get("stem", "")
        reference_answer = question.get("answer", "")
        scoring_rubric = question.get("scoring_rubric", "按要点给分")

        prompt = GRADING_USER_TEMPLATE.format(
            question_number=question_number,
            question_type=question_type,
            score=score,
            question_stem=stem,
            reference_answer=reference_answer,
            scoring_rubric=scoring_rubric,
            student_answer=student_answer,
        )

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": GRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            json_str = extract_json(response)
            if json_str:
                grading_result = json.loads(json_str)
            else:
                grading_result = None
            if isinstance(grading_result, dict):
                # 强制限制分数在 0～满分 之间
                q_score = question.get("score", 0)
                grading_result["score"] = max(0, min(int(grading_result.get("score", 0)), q_score))
                grading_result["suggested_score"] = grading_result["score"]
                return grading_result
            return {
                "score": 0,
                "overall_comment": "AI批改解析异常",
                "step_feedback": [],
                "error_analysis": "批改结果解析失败",
                "suggested_score": 0,
            }
        except Exception:
            return {
                "score": 0,
                "overall_comment": "AI批改服务暂时不可用",
                "step_feedback": [],
                "error_analysis": "AI服务异常",
                "suggested_score": 0,
            }

    async def grade_submission(
        self,
        assignment_id: str,
        submission_id: str,
        teacher_id: str,
        scores: list[dict] | None = None,
        teacher_feedback: str | None = None,
        confirm_ai_feedback: bool = False,
    ) -> dict | None:
        """批改单份提交 — 逐题评分，自动计算总分"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        stmt = select(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.id == submission_id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        )
        result = await self.db.execute(stmt)
        submission = result.scalar_one_or_none()
        if not submission:
            return None

        # 构建题目列表
        all_questions = []
        for section in (assignment.content or {}).get("sections", []):
            for q in section.get("questions", []):
                all_questions.append({
                    "number": q.get("number"),
                    "type": section.get("type", "objective"),
                    "max_score": q.get("score", 0),
                })

        # 计算作业总分
        max_score = assignment.total_score or sum(q["max_score"] for q in all_questions)

        # 构建逐题反馈
        question_feedback = []
        final_score = 0

        # 获取已有AI反馈中的客观题评分
        ai_qf_map: dict[int, dict] = {}
        if submission.ai_feedback:
            for qf in submission.ai_feedback.get("question_feedback", []):
                ai_qf_map[qf.get("question_number")] = qf

        if scores:
            # 教师提供了逐题评分，合并AI客观题+教师主观题
            scores_map = {s.get("question_number"): s.get("score", 0) for s in scores}
            for q in all_questions:
                q_num = q["number"]
                if q["type"] == "objective" and q_num in ai_qf_map:
                    # 客观题取AI自动评分
                    s = ai_qf_map[q_num].get("score", 0)
                    question_feedback.append(ai_qf_map[q_num])
                else:
                    # 主观题取教师评分
                    s = min(scores_map.get(q_num, 0), q["max_score"])
                    question_feedback.append({
                        "question_number": q_num,
                        "score": s,
                        "overall_comment": "教师评分",
                        "max_score": q["max_score"],
                    })
                final_score += s
        elif confirm_ai_feedback and submission.ai_feedback:
            # 确认AI批改
            for qf in submission.ai_feedback.get("question_feedback", []):
                question_feedback.append(qf)
                final_score += qf.get("score", 0)
        else:
            return None

        final_score = max(0, min(final_score, max_score))

        # 更新提交
        submission.ai_feedback = {
            "total_score": final_score,
            "question_feedback": question_feedback,
            "overall_comment": teacher_feedback or submission.ai_feedback.get("overall_comment", "") if submission.ai_feedback else teacher_feedback or "",
        }
        submission.score = final_score
        submission.teacher_feedback = teacher_feedback
        submission.teacher_id = teacher_id
        submission.status = "graded"
        submission.graded_at = datetime.utcnow()

        if submission.status == "graded":
            assignment.graded_count = (assignment.graded_count or 0) + 1

        return {
            "score": final_score,
            "max_score": max_score,
            "question_feedback": question_feedback,
            "teacher_feedback": teacher_feedback,
            "status": "graded",
        }

    async def batch_ai_grade(
        self, assignment_id: str, teacher_id: str, submission_ids: list[str] | None = None
    ) -> dict:
        """批量 AI 批改"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return {"success": False, "message": "无权操作此作业"}

        # 查询待批改的提交
        conditions = [
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.status.in_(["submitted"]),
        ]
        if submission_ids:
            conditions.append(AssignmentSubmission.id.in_(submission_ids))

        stmt = select(AssignmentSubmission).where(and_(*conditions))
        result = await self.db.execute(stmt)
        submissions = result.scalars().all()

        results = {"total": len(submissions), "success": 0, "failed": 0, "details": []}

        for submission in submissions:
            try:
                # 逐题批改
                content = submission.content
                assignment_content = assignment.content
                question_feedback = []
                total_score = 0

                all_questions = []
                for section in assignment_content.get("sections", []):
                    for q in section.get("questions", []):
                        q["section_type"] = section.get("type", "objective")
                        all_questions.append(q)

                # 构建学生答案映射
                answers_map = {}
                for ans in content.get("answers", []):
                    answers_map[ans.get("question_number")] = ans.get("answer", "")

                for q in all_questions:
                    q_num = q.get("number")
                    student_ans = answers_map.get(q_num, "")

                    if q.get("section_type") == "objective":
                        feedback = await self._grade_objective_question(q, student_ans)
                    else:
                        feedback = await self._grade_subjective_question(q, student_ans, q_num)

                    feedback["question_number"] = q_num
                    question_feedback.append(feedback)
                    total_score += feedback.get("score", 0)

                # 构建 AI 反馈
                ai_feedback = {
                    "total_score": total_score,
                    "question_feedback": question_feedback,
                    "overall_comment": f"AI 批改完成，总分 {total_score}",
                }

                # 判断是否全部为客观题（可自动确认）
                has_subjective = any(
                    q.get("section_type") == "subjective" for q in all_questions
                )
                submission.ai_feedback = ai_feedback
                submission.score = total_score

                if has_subjective:
                    # 含主观题 → 标记 grading，等待教师确认
                    submission.status = "grading"
                else:
                    # 纯客观题 → 直接确认，无需教师介入
                    submission.status = "graded"
                    submission.graded_at = datetime.utcnow()
                    assignment.graded_count = (assignment.graded_count or 0) + 1
                results["success"] += 1
                results["details"].append({
                    "submission_id": submission.id,
                    "status": "success",
                    "score": total_score,
                    "auto_confirmed": not has_subjective,
                })
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "submission_id": submission.id,
                    "status": "failed",
                    "error": str(e),
                })

        # 批量 flush
        await self.db.flush()
        return results

    async def return_submission(
        self, assignment_id: str, submission_id: str, teacher_id: str
    ) -> bool:
        """退回重做"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return False

        stmt = select(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.id == submission_id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        )
        result = await self.db.execute(stmt)
        submission = result.scalar_one_or_none()
        if not submission:
            return False

        submission.status = "returned"
        return True

    # ============================================================
    # 统计
    # ============================================================

    async def get_assignment_stats(self, assignment_id: str, teacher_id: str) -> dict | None:
        """获取作业统计"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        # 班级总人数
        cls = await self.db.get(Class, assignment.class_id)
        total_students = cls.student_count if cls else 0

        # 提交统计
        submitted_stmt = select(func.count()).select_from(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id
        )
        submitted_count = (await self.db.execute(submitted_stmt)).scalar() or 0

        graded_stmt = select(func.count()).select_from(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.status == "graded",
            )
        )
        graded_count = (await self.db.execute(graded_stmt)).scalar() or 0

        completion_rate = (submitted_count / total_students * 100) if total_students > 0 else 0.0

        # 平均分
        avg_stmt = select(func.avg(AssignmentSubmission.score)).where(
            and_(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.score.isnot(None),
            )
        )
        avg_score = (await self.db.execute(avg_stmt)).scalar()

        # 分数分布
        distribution = {"0-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
        scores_stmt = select(AssignmentSubmission.score).where(
            and_(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.score.isnot(None),
            )
        )
        scores_result = await self.db.execute(scores_stmt)
        for score in scores_result.scalars().all():
            if score < 60:
                distribution["0-59"] += 1
            elif score < 70:
                distribution["60-69"] += 1
            elif score < 80:
                distribution["70-79"] += 1
            elif score < 90:
                distribution["80-89"] += 1
            else:
                distribution["90-100"] += 1

        # 每题得分率（基于已批改提交的 AI 反馈）
        question_stats = []
        content = assignment.content or {}
        for section in content.get("sections", []):
            for q in section.get("questions", []):
                q_num = q.get("number")
                q_score = q.get("score", 0)
                question_stats.append({
                    "question_number": q_num,
                    "stem": q.get("stem", "")[:50],
                    "type": section.get("type"),
                    "max_score": q_score,
                    "average_score": None,  # 需要遍历提交计算，此处简化
                    "correct_rate": None,
                })

        return {
            "total_students": total_students,
            "submitted_count": submitted_count,
            "graded_count": graded_count,
            "completion_rate": round(completion_rate, 1),
            "average_score": round(float(avg_score), 1) if avg_score else None,
            "score_distribution": distribution,
            "question_stats": question_stats,
        }

    async def remind_unsubmitted(self, assignment_id: str, teacher_id: str) -> list[str] | None:
        """获取未提交学生列表（用于提醒）"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.teacher_id != teacher_id:
            return None

        # 已提交学生
        submitted_stmt = select(AssignmentSubmission.student_id).where(
            AssignmentSubmission.assignment_id == assignment_id
        )
        result = await self.db.execute(submitted_stmt)
        submitted_ids = set(result.scalars().all())

        # 班级所有学生
        roster_stmt = select(ClassStudent.student_id).where(
            ClassStudent.class_id == assignment.class_id
        )
        result = await self.db.execute(roster_stmt)
        all_student_ids = [row[0] for row in result.all()]

        return [sid for sid in all_student_ids if sid not in submitted_ids]

    # ============================================================
    # 学生端
    # ============================================================

    async def get_student_assignments(
        self,
        student_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict], int]:
        """获取学生的作业列表"""
        # 学生加入的班级
        class_subq = select(ClassStudent.class_id).where(
            ClassStudent.student_id == student_id
        )

        conditions = [
            Assignment.class_id.in_(class_subq),
            Assignment.status.in_(["active"]),
        ]

        count_stmt = (
            select(func.count()).select_from(Assignment).where(and_(*conditions))
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Assignment)
            .where(and_(*conditions))
            .options(selectinload(Assignment.class_))
            .order_by(Assignment.due_date.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        assignments = result.unique().scalars().all()

        items = []
        for a in assignments:
            # 查询该学生的提交状态
            sub_stmt = select(AssignmentSubmission).where(
                and_(
                    AssignmentSubmission.assignment_id == a.id,
                    AssignmentSubmission.student_id == student_id,
                )
            )
            sub_result = await self.db.execute(sub_stmt)
            submission = sub_result.scalar_one_or_none()

            my_status = "pending"
            if submission:
                if submission.status == "returned":
                    my_status = "returned"
                elif submission.status in ("graded",):
                    my_status = "graded"
                else:
                    my_status = "submitted"

            items.append({
                "id": a.id,
                "class_id": a.class_id,
                "class_name": a.class_.name if a.class_ else "",
                "title": a.title,
                "subject": a.subject,
                "total_score": a.total_score,
                "due_date": a.due_date,
                "allow_late_submission": a.allow_late_submission,
                "submission_count": a.submission_count,
                "graded_count": a.graded_count,
                "status": a.status,
                "my_status": my_status,
                "my_submission_id": submission.id if submission else None,
                "my_score": submission.score if submission and submission.status == "graded" else None,
                "created_at": a.created_at,
            })

        # 按状态筛选
        if status:
            items = [i for i in items if i["my_status"] == status]

        return items, total

    async def get_student_assignment_detail(self, assignment_id: str, student_id: str) -> dict | None:
        """学生查看作业详情"""
        stmt = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .options(selectinload(Assignment.class_))
        )
        result = await self.db.execute(stmt)
        a = result.unique().scalar_one_or_none()
        if not a:
            return None

        # 检查学生是否在该班级
        cs_result = await self.db.execute(
            select(ClassStudent).where(
                and_(
                    ClassStudent.class_id == a.class_id,
                    ClassStudent.student_id == student_id,
                )
            )
        )
        if not cs_result.scalar_one_or_none():
            return None

        return {
            "id": a.id,
            "class_id": a.class_id,
            "class_name": a.class_.name if a.class_ else "",
            "teacher_id": a.teacher_id,
            "title": a.title,
            "description": a.description,
            "subject": a.subject,
            "content": a.content,
            "total_score": a.total_score,
            "due_date": a.due_date,
            "allow_late_submission": a.allow_late_submission,
            "status": a.status,
            "created_at": a.created_at,
        }

    async def submit_assignment(
        self, assignment_id: str, student_id: str, content: dict, attachments: list | None = None
    ) -> str | None:
        """学生提交作业，返回状态消息"""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.status != "active":
            return "作业不存在或已关闭"

        # 检查是否在班级中
        cs_result = await self.db.execute(
            select(ClassStudent).where(
                and_(
                    ClassStudent.class_id == assignment.class_id,
                    ClassStudent.student_id == student_id,
                )
            )
        )
        if not cs_result.scalar_one_or_none():
            return "你不在该作业所属班级中"

        # 检查已有提交
        existing_stmt = select(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student_id,
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing and existing.status != "returned":
            return "你已提交过该作业，不可重复提交"

        # 检查截止时间
        now = datetime.utcnow()
        if assignment.due_date and now > assignment.due_date and not assignment.allow_late_submission:
            return "已过截止时间，该作业不允许迟交"

        if existing and existing.status == "returned":
            # 重新提交
            existing.content = content
            existing.attachments = attachments
            existing.status = "submitted"
            existing.submitted_at = now
            existing.score = None
            existing.ai_feedback = None
            existing.teacher_feedback = None
        else:
            # 新建提交
            submission = AssignmentSubmission(
                assignment_id=assignment_id,
                student_id=student_id,
                content=content,
                attachments=attachments,
                status="submitted",
                submitted_at=now,
            )
            self.db.add(submission)
            assignment.submission_count = (assignment.submission_count or 0) + 1

        await self.db.flush()
        return "ok"

    async def get_my_submission(self, assignment_id: str, student_id: str) -> dict | None:
        """学生查看自己的提交"""
        stmt = select(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        s = result.scalar_one_or_none()
        if not s:
            return None

        return {
            "id": s.id,
            "assignment_id": s.assignment_id,
            "student_id": s.student_id,
            "content": s.content,
            "attachments": s.attachments,
            "score": s.score,
            "ai_feedback": s.ai_feedback,
            "teacher_feedback": s.teacher_feedback,
            "status": s.status,
            "submitted_at": s.submitted_at,
            "graded_at": s.graded_at,
        }
