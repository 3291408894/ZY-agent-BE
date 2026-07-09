"""
班级试卷分享服务 — 教师分享试卷到班级 / 学生查看班级试卷
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.class_exam_paper import ClassExamPaper
from app.models.classes import Class, ClassStudent
from app.models.exam_paper import ExamPaper


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
        将试卷发送到指定班级。
        - 验证试卷存在且属于当前教师
        - 验证每个班级属于当前教师
        - 防重复发送（唯一约束）
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

        # 2. 验证班级归属
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

            # 3. 检查是否已分享
            existing = await self.db.scalar(
                select(ClassExamPaper).where(
                    ClassExamPaper.class_id == class_id,
                    ClassExamPaper.exam_paper_id == exam_paper_id,
                )
            )
            if existing:
                skipped.append(cls.name or class_id)
                continue

            # 4. 创建分享记录
            record = ClassExamPaper(
                id=str(uuid.uuid4()),
                class_id=class_id,
                exam_paper_id=exam_paper_id,
                shared_by=teacher_id,
            )
            self.db.add(record)
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
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return items, total

    # ================================================================
    # 学生端 — 验证学生属于该班级
    # ================================================================

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
