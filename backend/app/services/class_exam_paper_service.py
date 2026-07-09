"""
班级试卷分享服务 — 教师分享试卷到班级 / 学生查看班级试卷
分享试卷时自动创建对应作业，学生可在"我的作业"中在线答题
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.class_exam_paper import ClassExamPaper
from app.models.classes import Class, ClassStudent
from app.models.exam_paper import ExamPaper
from app.models.assignment import Assignment


# 试卷题型 → 作业分区类型映射
QUESTION_TYPE_TO_SECTION = {
    "choice":        "objective",
    "fill":          "subjective",
    "short_answer":  "subjective",
    "calculation":   "subjective",
    "analysis":      "subjective",
}


def _convert_exam_to_assignment_content(paper: ExamPaper) -> dict:
    """将试卷 content JSON 转换为作业 content JSON"""
    content = paper.content or {}

    # 收集所有题目并按分区类型重新分组
    sections_map: dict[str, list[dict]] = {}  # key: "objective" | "subjective"
    question_counter = 0

    for section in content.get("sections", []):
        for q in section.get("questions", []):
            question_counter += 1
            q_type = q.get("question_type", "short_answer")
            section_type = QUESTION_TYPE_TO_SECTION.get(q_type, "subjective")
            if section_type not in sections_map:
                sections_map[section_type] = []
            sections_map[section_type].append({
                "number":     question_counter,
                "stem":       q.get("stem", ""),
                "options":    q.get("options") if q_type == "choice" else None,
                "answer":     q.get("answer", ""),
                "score":      q.get("score", 0),
                "explanation":      q.get("analysis"),
                "scoring_rubric":   None,
            })

    # 构建作业分区列表
    new_sections = []
    for section_type in ("objective", "subjective"):
        questions = sections_map.get(section_type, [])
        if questions:
            new_sections.append({
                "type":      section_type,
                "title":     "客观题" if section_type == "objective" else "主观题",
                "questions": questions,
            })

    # 确定 format
    has_obj = "objective" in sections_map
    has_sub = "subjective" in sections_map
    if has_obj and has_sub:
        fmt = "mixed"
    elif has_obj:
        fmt = "objective_only"
    else:
        fmt = "subjective_only"

    return {
        "format":   fmt,
        "sections": new_sections,
    }


class ClassExamPaperService:
    """班级试卷分享服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # 教师端 — 发送试卷到班级
    # ================================================================

    async def send_to_classes(
        self,
        exam_paper_id: str,
        class_ids: list[str],
        teacher_id: str,
    ) -> dict:
        """
        将试卷发送到指定班级，同时为每个班级创建一份作业。
        - 验证试卷存在且属于当前教师
        - 验证每个班级属于当前教师
        - 防重复发送（唯一约束）
        - 创建 Assignment（学生可在"我的作业"在线答题）
        返回: { "success_count": int, "skipped": list[str], "errors": list[str] }
        """
        # 1. 验证试卷
        paper = await self.db.scalar(
            select(ExamPaper).where(
                ExamPaper.id == exam_paper_id,
                ExamPaper.status == "completed",
            )
        )
        if not paper:
            raise ValueError("试卷不存在")
        if paper.user_id != teacher_id:
            raise ValueError("无权分享此试卷，仅创建者可操作")

        # 2. 将试卷内容转换为作业内容（只做一次）
        assignment_content = _convert_exam_to_assignment_content(paper)
        total_score = paper.total_score or 0
        subject = paper.subject or ""

        # 3. 默认截止日期：7天后
        default_due = datetime.now(timezone.utc) + timedelta(days=7)

        # 4. 逐班级处理
        success_count = 0
        skipped: list[str] = []
        errors: list[str] = []

        for class_id in class_ids:
            cls = await self.db.scalar(
                select(Class).where(
                    Class.id == class_id,
                    Class.teacher_id == teacher_id,
                )
            )
            if not cls:
                errors.append(f"班级 {class_id} 不存在或无权操作")
                continue

            # 5. 检查是否已分享
            existing = await self.db.scalar(
                select(ClassExamPaper).where(
                    ClassExamPaper.class_id == class_id,
                    ClassExamPaper.exam_paper_id == exam_paper_id,
                )
            )
            if existing:
                skipped.append(cls.name or class_id)
                continue

            # 6. 创建分享记录
            record = ClassExamPaper(
                id=str(uuid.uuid4()),
                class_id=class_id,
                exam_paper_id=exam_paper_id,
                shared_by=teacher_id,
            )
            self.db.add(record)

            # 7. 创建对应作业（学生可在"我的作业"中看到并在线答题）
            assignment = Assignment(
                id=str(uuid.uuid4()),
                class_id=class_id,
                teacher_id=teacher_id,
                exam_paper_id=exam_paper_id,
                title=paper.title or f"{subject}试卷",
                description=f"试卷发送自教师，满分 {total_score} 分",
                subject=subject,
                content=assignment_content,
                total_score=total_score,
                due_date=default_due,
                allow_late_submission=True,
                status="active",
            )
            self.db.add(assignment)
            success_count += 1

        return {
            "success_count": success_count,
            "skipped": skipped,
            "errors": errors,
        }

    # ================================================================
    # 教师端 / 学生端共用 — 班级试卷列表
    # ================================================================

    async def list_class_exam_papers(
        self,
        class_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """查询班级已分享的试卷列表（分页），含试卷摘要信息"""
        # 验证班级存在
        cls = await self.db.scalar(select(Class).where(Class.id == class_id))
        if not cls:
            raise ValueError("班级不存在")

        # 总数
        count_q = select(func.count()).select_from(ClassExamPaper).where(
            ClassExamPaper.class_id == class_id
        )
        total = await self.db.scalar(count_q) or 0

        # 列表
        q = (
            select(ClassExamPaper)
            .where(ClassExamPaper.class_id == class_id)
            .options(
                joinedload(ClassExamPaper.exam_paper),
                joinedload(ClassExamPaper.sharer),
            )
            .order_by(ClassExamPaper.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        records = result.unique().scalars().all()

        items = []
        for r in records:
            paper = r.exam_paper
            sharer = r.sharer

            # 查找关联的作业（从试卷发布创建的）
            assignment = await self.db.scalar(
                select(Assignment).where(
                    and_(
                        Assignment.exam_paper_id == r.exam_paper_id,
                        Assignment.class_id == r.class_id,
                    )
                )
            )

            items.append({
                "id": r.id,
                "class_id": r.class_id,
                "class_name": cls.name,
                "exam_paper_id": r.exam_paper_id,
                "title": paper.title if paper else "",
                "subject": paper.subject if paper else "",
                "grade": paper.grade if paper else "",
                "exam_type": paper.exam_type if paper else "",
                "total_score": paper.total_score if paper else 0,
                "resource_type": "exam_paper",
                "shared_by": r.shared_by,
                "shared_by_name": sharer.nickname if sharer else "",
                "assignment_id": assignment.id if assignment else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return items, total

    # ================================================================
    # 学生端 — 验证学生属于该班级
    # ================================================================

    # ================================================================
    # 学生端 — 按需创建作业（在线作答入口）
    # ================================================================

    async def get_or_create_assignment_for_student(
        self,
        class_id: str,
        exam_paper_id: str,
        student_id: str,
    ) -> str:
        """
        获取或创建一个与试卷关联的作业，返回 assignment_id。

        - 如果该试卷在此班级已有作业，直接返回已有作业ID
        - 如果没有，则基于试卷内容自动创建作业（用于历史数据兼容和兜底）
        - 验证学生是否属于该班级
        """
        # 1. 验证学生属于该班级
        await self._verify_student_in_class(class_id, student_id)

        # 2. 验证分享记录存在
        share = await self.db.scalar(
            select(ClassExamPaper).where(
                and_(
                    ClassExamPaper.class_id == class_id,
                    ClassExamPaper.exam_paper_id == exam_paper_id,
                )
            )
        )
        if not share:
            raise ValueError("试卷未分享到此班级")

        # 3. 检查是否已有作业
        existing = await self.db.scalar(
            select(Assignment).where(
                and_(
                    Assignment.exam_paper_id == exam_paper_id,
                    Assignment.class_id == class_id,
                )
            )
        )
        if existing:
            return existing.id

        # 4. 获取试卷
        paper = await self.db.scalar(
            select(ExamPaper).where(
                and_(
                    ExamPaper.id == exam_paper_id,
                    ExamPaper.status == "completed",
                )
            )
        )
        if not paper:
            raise ValueError("试卷不存在或未生成完成")

        # 5. 基于试卷内容创建作业
        assignment_content = _convert_exam_to_assignment_content(paper)
        total_score = paper.total_score or 0
        subject = paper.subject or ""
        default_due = datetime.now(timezone.utc) + timedelta(days=7)

        assignment = Assignment(
            id=str(uuid.uuid4()),
            class_id=class_id,
            teacher_id=share.shared_by,
            exam_paper_id=exam_paper_id,
            title=paper.title or f"{subject}试卷",
            description=f"试卷，满分 {total_score} 分",
            subject=subject,
            content=assignment_content,
            total_score=total_score,
            due_date=default_due,
            allow_late_submission=True,
            status="active",
        )
        self.db.add(assignment)
        await self.db.flush()

        return assignment.id

    async def _verify_student_in_class(self, class_id: str, student_id: str) -> Class:
        """验证学生属于指定班级，返回 Class 对象"""
        cls = await self.db.scalar(
            select(Class).where(Class.id == class_id, Class.status == "active")
        )
        if not cls:
            raise ValueError("班级不存在或已归档")

        membership = await self.db.scalar(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == student_id,
            )
        )
        if not membership:
            raise ValueError("你尚未加入该班级")

        return cls
