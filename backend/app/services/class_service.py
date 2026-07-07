"""
班级管理服务 (功能4) — 创建/加入/退出/花名册/邀请码
"""

from datetime import datetime, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.classes import Class, ClassStudent, generate_invite_code
from app.models.user import User


class ClassService:
    """班级管理业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 教师端
    # ============================================================

    async def create_class(
        self, teacher_id: str, name: str, grade: str, subject: str, description: str | None
    ) -> Class:
        """创建班级，自动生成唯一邀请码"""
        # 生成唯一邀请码
        code = generate_invite_code()
        while True:
            existing = await self.db.execute(
                select(Class).where(Class.invite_code == code)
            )
            if not existing.scalar():
                break
            code = generate_invite_code()

        new_class = Class(
            teacher_id=teacher_id,
            name=name,
            grade=grade,
            subject=subject,
            description=description,
            invite_code=code,
        )
        self.db.add(new_class)
        await self.db.flush()
        now = datetime.now(timezone.utc)
        return {
            "id": new_class.id,
            "teacher_id": new_class.teacher_id,
            "name": new_class.name,
            "grade": new_class.grade,
            "subject": new_class.subject,
            "description": new_class.description,
            "invite_code": new_class.invite_code,
            "student_count": new_class.student_count,
            "status": new_class.status,
            "created_at": now,
            "updated_at": now,
        }

    async def get_teacher_classes(
        self,
        teacher_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict], int]:
        """获取教师创建的班级列表"""
        conditions = [Class.teacher_id == teacher_id]
        if status:
            conditions.append(Class.status == status)

        # 总数
        count_stmt = select(func.count()).select_from(Class).where(and_(*conditions))
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 列表
        stmt = (
            select(Class)
            .where(and_(*conditions))
            .order_by(Class.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        classes = result.unique().scalars().all()

        items = []
        for c in classes:
            items.append({
                "id": c.id,
                "teacher_id": c.teacher_id,
                "name": c.name,
                "grade": c.grade,
                "subject": c.subject,
                "description": c.description,
                "invite_code": c.invite_code,
                "student_count": c.student_count,
                "status": c.status,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            })
        return items, total

    async def get_class_detail(self, class_id: str, teacher_id: str) -> dict | None:
        """获取班级详情（含花名册）"""
        stmt = (
            select(Class)
            .where(and_(Class.id == class_id, Class.teacher_id == teacher_id))
            .options(selectinload(Class.students_rel).selectinload(ClassStudent.student))
        )
        result = await self.db.execute(stmt)
        cls = result.unique().scalar_one_or_none()
        if not cls:
            return None

        students = []
        for cs in cls.students_rel:
            students.append({
                "id": cs.id,
                "student_id": cs.student_id,
                "nickname": cs.student.nickname if cs.student else "未知",
                "avatar_url": cs.student.avatar_url if cs.student else None,
                "joined_at": cs.joined_at,
            })

        return {
            "id": cls.id,
            "teacher_id": cls.teacher_id,
            "name": cls.name,
            "grade": cls.grade,
            "subject": cls.subject,
            "description": cls.description,
            "invite_code": cls.invite_code,
            "student_count": cls.student_count,
            "status": cls.status,
            "created_at": cls.created_at,
            "updated_at": cls.updated_at,
            "students": students,
        }

    async def get_roster(self, class_id: str, teacher_id: str) -> dict | None:
        """获取花名册"""
        return await self.get_class_detail(class_id, teacher_id)

    async def remove_student(self, class_id: str, student_id: str, teacher_id: str) -> bool:
        """教师移除学生"""
        # 验证班级归属
        cls = await self.db.get(Class, class_id)
        if not cls or cls.teacher_id != teacher_id:
            return False

        # 删除关联
        stmt = select(ClassStudent).where(
            and_(ClassStudent.class_id == class_id, ClassStudent.student_id == student_id)
        )
        result = await self.db.execute(stmt)
        cs = result.scalar_one_or_none()
        if not cs:
            return False

        await self.db.delete(cs)

        # 更新学生计数
        cls.student_count = max(0, cls.student_count - 1)
        return True

    async def regenerate_invite_code(self, class_id: str, teacher_id: str) -> str | None:
        """重新生成邀请码（旧码立即失效）"""
        cls = await self.db.get(Class, class_id)
        if not cls or cls.teacher_id != teacher_id:
            return None

        code = generate_invite_code()
        while True:
            existing = await self.db.execute(
                select(Class).where(Class.invite_code == code)
            )
            if not existing.scalar():
                break
            code = generate_invite_code()

        cls.invite_code = code
        return code

    async def archive_class(self, class_id: str, teacher_id: str) -> bool:
        """归档班级"""
        cls = await self.db.get(Class, class_id)
        if not cls or cls.teacher_id != teacher_id:
            return False
        cls.status = "archived"
        return True

    # ============================================================
    # 学生端
    # ============================================================

    async def get_class_by_invite_code(self, invite_code: str) -> dict | None:
        """通过邀请码查找班级（学生加入前确认信息）"""
        stmt = (
            select(Class)
            .where(and_(Class.invite_code == invite_code, Class.status == "active"))
            .options(selectinload(Class.teacher))
        )
        result = await self.db.execute(stmt)
        cls = result.unique().scalar_one_or_none()
        if not cls:
            return None

        return {
            "class_id": cls.id,
            "class_name": cls.name,
            "teacher_name": cls.teacher.nickname if cls.teacher else "未知",
            "subject": cls.subject,
            "grade": cls.grade,
        }

    async def join_class(self, student_id: str, invite_code: str) -> str | None:
        """学生通过邀请码加入班级，返回班级ID，失败返回None"""
        # 查找班级
        stmt = select(Class).where(
            and_(Class.invite_code == invite_code, Class.status == "active")
        )
        result = await self.db.execute(stmt)
        cls = result.scalar_one_or_none()
        if not cls:
            return None

        # 检查是否已在班级中
        existing = await self.db.execute(
            select(ClassStudent).where(
                and_(ClassStudent.class_id == cls.id, ClassStudent.student_id == student_id)
            )
        )
        if existing.scalar_one_or_none():
            return "already_joined"

        # 加入
        cs = ClassStudent(class_id=cls.id, student_id=student_id)
        self.db.add(cs)

        # 更新计数
        cls.student_count = (cls.student_count or 0) + 1
        await self.db.flush()
        return cls.id

    async def leave_class(self, class_id: str, student_id: str) -> bool:
        """学生退出班级"""
        stmt = select(ClassStudent).where(
            and_(ClassStudent.class_id == class_id, ClassStudent.student_id == student_id)
        )
        result = await self.db.execute(stmt)
        cs = result.scalar_one_or_none()
        if not cs:
            return False

        await self.db.delete(cs)

        # 更新计数
        cls = await self.db.get(Class, class_id)
        if cls:
            cls.student_count = max(0, (cls.student_count or 1) - 1)
        return True

    async def get_student_classes(
        self, student_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """获取学生加入的班级列表"""
        # 子查询获取学生加入的班级ID
        subq = select(ClassStudent.class_id).where(ClassStudent.student_id == student_id)

        count_stmt = (
            select(func.count())
            .select_from(Class)
            .where(and_(Class.id.in_(subq), Class.status == "active"))
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Class, ClassStudent.joined_at)
            .join(ClassStudent, and_(ClassStudent.class_id == Class.id))
            .where(and_(ClassStudent.student_id == student_id, Class.status == "active"))
            .options(selectinload(Class.teacher))
            .order_by(ClassStudent.joined_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        rows = result.unique().all()

        items = []
        for cls, joined_at in rows:
            items.append({
                "id": cls.id,
                "name": cls.name,
                "grade": cls.grade,
                "subject": cls.subject,
                "teacher_name": cls.teacher.nickname if cls.teacher else "未知",
                "student_count": cls.student_count,
                "joined_at": joined_at,
            })
        return items, total
