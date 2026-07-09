"""
班级资源分享服务 — 教师分享资源到班级 / 学生查看与保存
"""

import os
import shutil
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.class_resource import ClassResource
from app.models.classes import Class, ClassStudent
from app.models.teaching_resource import TeachingResource
from app.models.file import UploadedFile


class ClassResourceService:
    """班级资源分享服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # 教师端 — 发送资源到班级
    # ================================================================

    async def send_to_classes(
        self,
        resource_id: str,
        class_ids: list[str],
        teacher_id: str,
    ) -> dict:
        """
        将教学资源发送到指定班级。
        - 验证资源存在且可用
        - 验证每个班级属于当前教师
        - 防重复发送（唯一约束）
        返回: { "success_count": int, "skipped": list[str], "errors": list[str] }
        """
        # 1. 验证资源
        resource = await self.db.scalar(
            select(TeachingResource).where(
                TeachingResource.id == resource_id,
                TeachingResource.status == "active",
            )
        )
        if not resource:
            raise ValueError("资源不存在或已被删除")

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
                select(ClassResource).where(
                    ClassResource.class_id == class_id,
                    ClassResource.resource_id == resource_id,
                )
            )
            if existing:
                skipped.append(cls.name or class_id)
                continue

            # 4. 创建分享记录
            record = ClassResource(
                id=str(uuid.uuid4()),
                class_id=class_id,
                resource_id=resource_id,
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
    # 教师端 / 学生端共用 — 班级资源列表
    # ================================================================

    async def list_class_resources(
        self,
        class_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """查询班级已分享的资源列表（分页），含资源摘要信息"""
        # 验证班级存在
        cls = await self.db.scalar(select(Class).where(Class.id == class_id))
        if not cls:
            raise ValueError("班级不存在")

        # 总数
        count_q = select(func.count()).select_from(ClassResource).where(
            ClassResource.class_id == class_id
        )
        total = await self.db.scalar(count_q) or 0

        # 列表
        q = (
            select(ClassResource)
            .where(ClassResource.class_id == class_id)
            .options(
                joinedload(ClassResource.resource),
                joinedload(ClassResource.sharer),
            )
            .order_by(ClassResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        records = result.unique().scalars().all()

        items = []
        for r in records:
            res = r.resource
            sharer = r.sharer
            items.append({
                "id": r.id,
                "class_id": r.class_id,
                "class_name": cls.name,
                "resource_id": r.resource_id,
                "resource_title": res.title if res else "",
                "resource_file_type": res.file_type if res else "",
                "resource_file_name": res.file_name if res else "",
                "resource_file_size": res.file_size if res else 0,
                "resource_subject": res.subject if res else "",
                "resource_grade": res.grade if res else "",
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

    # ================================================================
    # 学生端 — 保存资源到知识库
    # ================================================================

    async def save_to_knowledge(
        self,
        class_id: str,
        resource_id: str,
        student_id: str,
    ) -> dict:
        """
        学生将班级共享资源保存到自己的知识库。
        流程:
        1. 验证学生属于该班级
        2. 验证资源已分享到该班级
        3. 读取源文件，复制到学生的上传文件目录
        4. 创建 uploaded_files 记录（状态为 done）
        返回: { "file_id": str, "filename": str }
        """
        # 1. 验证学生属于该班级
        cls = await self._verify_student_in_class(class_id, student_id)

        # 2. 验证资源已分享到该班级
        share = await self.db.scalar(
            select(ClassResource).where(
                ClassResource.class_id == class_id,
                ClassResource.resource_id == resource_id,
            )
        )
        if not share:
            raise ValueError("该资源尚未分享到此班级")

        # 3. 获取资源文件信息
        resource = await self.db.scalar(
            select(TeachingResource).where(
                TeachingResource.id == resource_id,
                TeachingResource.status == "active",
            )
        )
        if not resource:
            raise ValueError("资源不存在")

        # 4. 复制文件到学生上传目录
        src_path = resource.file_path
        if not src_path or not os.path.isfile(src_path):
            raise ValueError("资源文件缺失")

        # 学生上传目录: {UPLOAD_DIR}/files/{user_id}/
        student_dir = os.path.join(settings.UPLOAD_DIR, "files", student_id)
        os.makedirs(student_dir, exist_ok=True)

        file_id = str(uuid.uuid4())
        ext = resource.file_ext
        dst_filename = f"{resource.file_name}"
        dst_path = os.path.join(student_dir, f"{file_id}.{ext}")

        shutil.copy2(src_path, dst_path)

        # 5. 映射 file_type 到 uploaded_files 支持的类型
        FILE_TYPE_MAP = {
            "pdf": "pdf", "docx": "docx", "txt": "txt",
            "pptx": "txt", "xlsx": "txt", "image": "txt",
            "mp4": "txt", "mp3": "txt", "zip": "txt",
        }
        upload_file_type = FILE_TYPE_MAP.get(resource.file_type, "txt")

        # 6. 创建 uploaded_files 记录
        upload_record = UploadedFile(
            id=file_id,
            user_id=student_id,
            filename=dst_filename,
            file_type=upload_file_type,
            file_size=resource.file_size,
            storage_path=dst_path,
            parse_status="done",
            parsed_content=f"来自班级「{cls.name}」的共享资源：{resource.title}",
        )
        self.db.add(upload_record)

        return {
            "file_id": file_id,
            "filename": dst_filename,
        }
