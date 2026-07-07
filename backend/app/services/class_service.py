"""
班级管理服务层 — 创建班级、邀请码生成、加入/退出、花名册、归档
"""

import secrets
import string

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classes import Class, ClassStudent
from app.models.user import User

# 邀请码字符集（排除易混淆字符 0/O/1/I/L）
_INVITE_CODE_ALPHABET = [
    c for c in string.ascii_uppercase + string.digits
    if c not in {"0", "O", "1", "I", "L"}
]
_INVITE_CODE_LENGTH = 8


class ClassService:
    """班级管理业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================================================================
    # 教师端
    # ==================================================================

    async def create_class(
        self, teacher_id: str, name: str, grade: str, subject: str, description: str | None
    ) -> Class:
        """创建班级，自动生成唯一邀请码"""
        invite_code = await self._generate_unique_code()

        cls = Class(
            teacher_id=teacher_id,
            name=name.strip(),
            grade=grade.strip(),
            subject=subject.strip(),
            description=description.strip() if description else None,
            invite_code=invite_code,
        )
        self.db.add(cls)
        await self.db.flush()
        logger.info(
            f"班级已创建 | id={cls.id} | name={cls.name} | "
            f"teacher={teacher_id} | invite_code={invite_code}"
        )
        return cls

    async def get_teacher_classes(self, teacher_id: str) -> list[Class]:
        """教师端：我的班级列表（按更新时间倒序）"""
        stmt = (
            select(Class)
            .where(Class.teacher_id == teacher_id)
            .order_by(desc(Class.updated_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_class_detail(self, class_id: str, teacher_id: str) -> Class | None:
        """教师端：班级详情（校验归属）"""
        return await self._get_owned_class(class_id, teacher_id)

    async def get_roster(self, class_id: str, teacher_id: str) -> list[dict] | None:
        """教师端：班级花名册"""
        cls = await self._get_owned_class(class_id, teacher_id)
        if not cls:
            return None

        stmt = (
            select(ClassStudent, User.nickname)
            .join(User, ClassStudent.student_id == User.id)
            .where(ClassStudent.class_id == class_id)
            .order_by(ClassStudent.joined_at)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row.ClassStudent.id,
                "student_id": row.ClassStudent.student_id,
                "student_name": row.nickname or "同学",
                "joined_at": row.ClassStudent.joined_at,
            }
            for row in rows
        ]

    async def remove_student(
        self, class_id: str, teacher_id: str, student_id: str
    ) -> bool:
        """教师端：从班级移除学生"""
        cls = await self._get_owned_class(class_id, teacher_id)
        if not cls:
            return False

        stmt = select(ClassStudent).where(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()
        if not membership:
            return False

        await self.db.delete(membership)
        cls.student_count = max(0, cls.student_count - 1)
        await self.db.flush()
        logger.info(f"学生已移除 | class={class_id} | student={student_id}")
        return True

    async def regenerate_invite_code(
        self, class_id: str, teacher_id: str
    ) -> str | None:
        """教师端：重新生成邀请码（旧码立即失效）"""
        cls = await self._get_owned_class(class_id, teacher_id)
        if not cls:
            return None
        if cls.status == "archived":
            return None

        new_code = await self._generate_unique_code()
        cls.invite_code = new_code
        await self.db.flush()
        logger.info(f"邀请码已更新 | class={class_id} | new_code={new_code}")
        return new_code

    async def archive_class(self, class_id: str, teacher_id: str) -> Class | None:
        """教师端：归档班级"""
        cls = await self._get_owned_class(class_id, teacher_id)
        if not cls:
            return None
        cls.status = "archived"
        await self.db.flush()
        logger.info(f"班级已归档 | class={class_id}")
        return cls

    # ==================================================================
    # 学生端
    # ==================================================================

    async def join_by_code(self, student_id: str, invite_code: str) -> dict:
        """
        学生通过邀请码加入班级

        Returns:
            {"success": True, "class_id": "...", "class_name": "..."}
        Raises:
            ValueError: 邀请码无效 / 已在班级中
        """
        # 1. 查找班级
        stmt = select(Class).where(Class.invite_code == invite_code.upper().strip())
        result = await self.db.execute(stmt)
        cls = result.scalar_one_or_none()

        if not cls:
            raise ValueError("邀请码无效，请检查后重试")
        if cls.status == "archived":
            raise ValueError("该班级已归档，无法加入")

        # 2. 校验是否已在班级中
        existing = await self.db.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == cls.id,
                ClassStudent.student_id == student_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("你已在该班级中，无需重复加入")

        # 3. 加入
        membership = ClassStudent(class_id=cls.id, student_id=student_id)
        self.db.add(membership)
        cls.student_count += 1
        await self.db.flush()

        logger.info(f"学生加入班级 | student={student_id} | class={cls.id} | name={cls.name}")
        return {
            "success": True,
            "class_id": cls.id,
            "class_name": cls.name,
        }

    async def get_student_classes(self, student_id: str) -> list[dict]:
        """学生端：我加入的班级列表"""
        stmt = (
            select(Class, ClassStudent.joined_at)
            .join(ClassStudent, ClassStudent.class_id == Class.id)
            .where(ClassStudent.student_id == student_id)
            .order_by(desc(ClassStudent.joined_at))
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row.Class.id,
                "name": row.Class.name,
                "grade": row.Class.grade,
                "subject": row.Class.subject,
                "description": row.Class.description,
                "status": row.Class.status,
                "joined_at": row.joined_at,
            }
            for row in rows
        ]

    async def leave_class(self, class_id: str, student_id: str) -> bool:
        """学生端：退出班级"""
        stmt = select(ClassStudent).where(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()
        if not membership:
            return False

        cls = await self.db.get(Class, class_id)
        await self.db.delete(membership)
        if cls:
            cls.student_count = max(0, cls.student_count - 1)
        await self.db.flush()
        logger.info(f"学生退出班级 | student={student_id} | class={class_id}")
        return True

    # ==================================================================
    # 内部
    # ==================================================================

    async def _get_owned_class(self, class_id: str, teacher_id: str) -> Class | None:
        """获取属于指定教师的班级"""
        stmt = select(Class).where(
            Class.id == class_id,
            Class.teacher_id == teacher_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _generate_unique_code(self) -> str:
        """生成全局唯一的 8 位邀请码"""
        for _ in range(100):  # 最多尝试 100 次
            code = "".join(
                secrets.choice(_INVITE_CODE_ALPHABET)
                for _ in range(_INVITE_CODE_LENGTH)
            )
            stmt = select(Class).where(Class.invite_code == code)
            result = await self.db.execute(stmt)
            if not result.scalar_one_or_none():
                return code
        raise RuntimeError("无法生成唯一邀请码，请稍后重试")
