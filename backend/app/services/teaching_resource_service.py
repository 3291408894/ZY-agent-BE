"""
教学资源库服务层 — 上传/下载/列表/搜索/收藏/删除 (功能3)
"""

import os
import uuid
from pathlib import Path

import aiofiles
from loguru import logger
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import settings
from app.models.teaching_resource import (
    ResourceDownloadLog,
    ResourceFavorite,
    TeachingResource,
)
from app.models.user import User
from app.schemas.teaching_resource import (
    ALLOWED_EXTENSIONS,
    EXT_TO_FILE_TYPE,
    FILE_TYPE_LABELS,
    RESOURCE_TYPE_LABELS,
)


class TeachingResourceService:
    """教学资源库业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 文件类型分类 ───────────────────────────────────────

    @staticmethod
    def classify_file_type(ext: str) -> str:
        """根据扩展名归类到 file_type"""
        ext = ext.lower().lstrip(".")
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: .{ext}")
        return EXT_TO_FILE_TYPE.get(ext, "other")

    # ── 上传 ───────────────────────────────────────────────

    async def upload(
        self,
        user_id: str,
        title: str,
        subject: str,
        grade: str,
        resource_type: str,
        visibility: str,
        filename: str,
        content: bytes,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> TeachingResource:
        """上传教学资源"""
        # 校验扩展名
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: .{ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

        file_type = self.classify_file_type(ext)

        # 校验文件大小
        max_size = settings.max_file_size_bytes
        if len(content) > max_size:
            raise ValueError(f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)")

        resource_id = str(uuid.uuid4())

        # 按用户分目录存储
        user_dir = Path(settings.UPLOAD_DIR) / "resources" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_path = str(user_dir / f"{resource_id}.{ext}")

        # 写入磁盘
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(content)

        # 生成搜索关键词
        keywords = f"{title} {subject} {grade} {RESOURCE_TYPE_LABELS.get(resource_type, '')} {' '.join(tags or [])}"

        record = TeachingResource(
            id=resource_id,
            uploader_id=user_id,
            title=title,
            description=description,
            subject=subject,
            grade=grade,
            resource_type=resource_type,
            file_type=file_type,
            file_name=filename,
            file_path=storage_path,
            file_size=len(content),
            file_ext=ext,
            visibility=visibility,
            tags=tags or [],
            keywords=keywords,
            status="active",
        )
        self.db.add(record)
        await self.db.flush()
        logger.info(f"资源上传成功: {title} ({resource_id}) by user {user_id}")
        return record

    # ── 列表查询（资源广场） ──────────────────────────────────

    async def list_resources(
        self,
        current_user_id: str,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        subject: str | None = None,
        grade: str | None = None,
        resource_type: str | None = None,
        file_type: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        """
        资源广场列表：
        - public 资源所有人可见
        - private 资源仅上传者可见（我的资源用单独接口）
        - 支持关键词全文搜索、筛选、排序
        """
        conditions = [
            TeachingResource.status == "active",
            TeachingResource.visibility == "public",
        ]

        if subject:
            conditions.append(TeachingResource.subject == subject)
        if grade:
            conditions.append(TeachingResource.grade == grade)
        if resource_type:
            conditions.append(TeachingResource.resource_type == resource_type)
        if file_type:
            conditions.append(TeachingResource.file_type == file_type)
        if keyword:
            # 使用 LIKE 搜索（兼容无 FULLTEXT 索引的情况）
            like_pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    TeachingResource.title.like(like_pattern),
                    TeachingResource.description.like(like_pattern),
                    TeachingResource.keywords.like(like_pattern),
                )
            )

        # 计数
        count_stmt = (
            select(func.count())
            .select_from(TeachingResource)
            .where(and_(*conditions))
        )
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 排序字段白名单校验
        allowed_sort_fields = {"created_at", "download_count", "like_count", "updated_at"}
        if sort_by not in allowed_sort_fields:
            sort_by = "created_at"
        sort_col = getattr(TeachingResource, sort_by)
        if sort_order == "asc":
            sort_col = sort_col.asc()
        else:
            sort_col = sort_col.desc()

        # 列表查询（eager load uploader）
        stmt = (
            select(TeachingResource)
            .where(and_(*conditions))
            .options(joinedload(TeachingResource.uploader))
            .order_by(sort_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        resources = list(result.unique().scalars().all())

        # 查询当前用户的收藏状态
        favorited_ids: set[str] = set()
        if resources:
            fav_stmt = select(ResourceFavorite.resource_id).where(
                ResourceFavorite.user_id == current_user_id,
                ResourceFavorite.resource_id.in_([r.id for r in resources]),
            )
            fav_result = await self.db.execute(fav_stmt)
            favorited_ids = {row[0] for row in fav_result.fetchall()}

        items = []
        for r in resources:
            items.append({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "subject": r.subject,
                "grade": r.grade,
                "resource_type": r.resource_type,
                "resource_type_label": RESOURCE_TYPE_LABELS.get(r.resource_type, r.resource_type),
                "file_type": r.file_type,
                "file_type_label": FILE_TYPE_LABELS.get(r.file_type, r.file_type),
                "file_name": r.file_name,
                "file_size": r.file_size,
                "file_ext": r.file_ext,
                "download_count": r.download_count,
                "view_count": r.view_count,
                "like_count": r.like_count,
                "visibility": r.visibility,
                "tags": r.tags,
                "is_favorited": r.id in favorited_ids,
                "uploader": {
                    "id": r.uploader.id,
                    "nickname": r.uploader.nickname,
                    "avatar_url": r.uploader.avatar_url,
                } if r.uploader else None,
                "created_at": r.created_at,
            })

        return items, total

    # ── 我的资源 ────────────────────────────────────────────

    async def list_my_resources(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        resource_type: str | None = None,
        visibility: str | None = None,
    ) -> tuple[list[dict], int]:
        """我的上传资源列表（含私有资源）"""
        conditions = [
            TeachingResource.uploader_id == user_id,
            TeachingResource.status == "active",
        ]
        if resource_type:
            conditions.append(TeachingResource.resource_type == resource_type)
        if visibility:
            conditions.append(TeachingResource.visibility == visibility)

        count_stmt = (
            select(func.count())
            .select_from(TeachingResource)
            .where(and_(*conditions))
        )
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        stmt = (
            select(TeachingResource)
            .where(and_(*conditions))
            .order_by(TeachingResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        resources = list(result.scalars().all())

        items = []
        for r in resources:
            items.append({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "subject": r.subject,
                "grade": r.grade,
                "resource_type": r.resource_type,
                "resource_type_label": RESOURCE_TYPE_LABELS.get(r.resource_type, r.resource_type),
                "file_type": r.file_type,
                "file_type_label": FILE_TYPE_LABELS.get(r.file_type, r.file_type),
                "file_name": r.file_name,
                "file_size": r.file_size,
                "file_ext": r.file_ext,
                "download_count": r.download_count,
                "view_count": r.view_count,
                "like_count": r.like_count,
                "visibility": r.visibility,
                "tags": r.tags,
                "is_favorited": False,  # 自己的资源不展示收藏状态
                "uploader": None,       # 自己的资源不展示上传者
                "created_at": r.created_at,
            })

        return items, total

    # ── 详情 ────────────────────────────────────────────────

    async def get_detail(
        self,
        resource_id: str,
        current_user_id: str | None = None,
    ) -> dict | None:
        """获取资源详情（含上传者信息、收藏状态）"""
        stmt = (
            select(TeachingResource)
            .where(
                TeachingResource.id == resource_id,
                TeachingResource.status == "active",
            )
            .options(joinedload(TeachingResource.uploader))
        )
        result = await self.db.execute(stmt)
        r = result.unique().scalar_one_or_none()
        if not r:
            return None

        # 可见性检查：private 仅上传者可见
        if r.visibility == "private":
            if current_user_id is None or r.uploader_id != current_user_id:
                return None

        # 收藏状态
        is_favorited = False
        if current_user_id:
            fav_stmt = select(ResourceFavorite).where(
                ResourceFavorite.user_id == current_user_id,
                ResourceFavorite.resource_id == resource_id,
            )
            fav_result = await self.db.execute(fav_stmt)
            is_favorited = fav_result.scalar_one_or_none() is not None

        # 浏览计数 +1
        r.view_count += 1
        self.db.add(r)
        await self.db.flush()

        return {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "subject": r.subject,
            "grade": r.grade,
            "resource_type": r.resource_type,
            "resource_type_label": RESOURCE_TYPE_LABELS.get(r.resource_type, r.resource_type),
            "file_type": r.file_type,
            "file_type_label": FILE_TYPE_LABELS.get(r.file_type, r.file_type),
            "file_name": r.file_name,
            "file_size": r.file_size,
            "file_ext": r.file_ext,
            "download_count": r.download_count,
            "view_count": r.view_count,
            "like_count": r.like_count,
            "visibility": r.visibility,
            "tags": r.tags,
            "keywords": r.keywords,
            "status": r.status,
            "is_favorited": is_favorited,
            "uploader": {
                "id": r.uploader.id,
                "nickname": r.uploader.nickname,
                "avatar_url": r.uploader.avatar_url,
            } if r.uploader else None,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }

    # ── 下载 ────────────────────────────────────────────────

    async def download(
        self,
        resource_id: str,
        current_user_id: str,
    ) -> tuple[str, str, str] | None:
        """
        下载资源文件，返回 (file_path, file_name, file_ext)。
        记录下载日志并增加下载计数。
        """
        r = await self.db.get(TeachingResource, resource_id)
        if not r or r.status != "active":
            return None

        # 可见性检查
        if r.visibility == "private" and r.uploader_id != current_user_id:
            return None

        # 检查文件是否存在
        if not os.path.exists(r.file_path):
            logger.error(f"资源文件缺失: {r.file_path}")
            return None

        # 下载计数 +1
        r.download_count += 1
        self.db.add(r)

        # 记录下载日志
        log = ResourceDownloadLog(
            user_id=current_user_id,
            resource_id=resource_id,
        )
        self.db.add(log)
        await self.db.flush()

        return (r.file_path, r.file_name, r.file_ext)

    # ── 软删除 ──────────────────────────────────────────────

    async def soft_delete(self, resource_id: str, user_id: str) -> bool:
        """软删除资源（仅上传者可操作）"""
        r = await self.db.get(TeachingResource, resource_id)
        if not r or r.status != "active":
            return False
        if r.uploader_id != user_id:
            return False

        r.status = "deleted"
        self.db.add(r)
        await self.db.flush()
        logger.info(f"资源已软删除: {resource_id} by user {user_id}")
        return True

    # ── 收藏/取消收藏 ───────────────────────────────────────

    async def toggle_favorite(
        self,
        resource_id: str,
        user_id: str,
    ) -> dict:
        """切换收藏状态，返回 {is_favorited, resource_id}"""
        # 校验资源存在且可见
        r = await self.db.get(TeachingResource, resource_id)
        if not r or r.status != "active":
            raise ValueError("资源不存在")
        if r.visibility == "private" and r.uploader_id != user_id:
            raise ValueError("资源不存在")

        # 查找已有收藏
        stmt = select(ResourceFavorite).where(
            ResourceFavorite.user_id == user_id,
            ResourceFavorite.resource_id == resource_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # 取消收藏
            await self.db.delete(existing)
            if r.like_count > 0:
                r.like_count -= 1
                self.db.add(r)
            await self.db.flush()
            return {"is_favorited": False, "resource_id": resource_id}
        else:
            # 添加收藏
            fav = ResourceFavorite(
                user_id=user_id,
                resource_id=resource_id,
            )
            self.db.add(fav)
            r.like_count += 1
            self.db.add(r)
            await self.db.flush()
            return {"is_favorited": True, "resource_id": resource_id}

    # ── 我的收藏列表 ────────────────────────────────────────

    async def list_my_favorites(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """获取当前用户的收藏列表"""
        # 计数
        count_stmt = (
            select(func.count())
            .select_from(ResourceFavorite)
            .join(TeachingResource, ResourceFavorite.resource_id == TeachingResource.id)
            .where(
                ResourceFavorite.user_id == user_id,
                TeachingResource.status == "active",
            )
        )
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 列表
        stmt = (
            select(ResourceFavorite)
            .where(ResourceFavorite.user_id == user_id)
            .options(
                joinedload(ResourceFavorite.resource).joinedload(TeachingResource.uploader)
            )
            .order_by(ResourceFavorite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        favs = list(result.unique().scalars().all())

        items = []
        for fav in favs:
            r = fav.resource
            if not r or r.status != "active":
                continue
            items.append({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "subject": r.subject,
                "grade": r.grade,
                "resource_type": r.resource_type,
                "resource_type_label": RESOURCE_TYPE_LABELS.get(r.resource_type, r.resource_type),
                "file_type": r.file_type,
                "file_type_label": FILE_TYPE_LABELS.get(r.file_type, r.file_type),
                "file_name": r.file_name,
                "file_size": r.file_size,
                "file_ext": r.file_ext,
                "download_count": r.download_count,
                "view_count": r.view_count,
                "like_count": r.like_count,
                "visibility": r.visibility,
                "tags": r.tags,
                "is_favorited": True,
                "uploader": {
                    "id": r.uploader.id,
                    "nickname": r.uploader.nickname,
                    "avatar_url": r.uploader.avatar_url,
                } if r.uploader else None,
                "created_at": r.created_at,
                "favorited_at": fav.created_at,
            })

        return items, total

    # ── 筛选选项 ────────────────────────────────────────────

    async def get_filter_options(self) -> dict:
        """获取筛选下拉选项（学科、年级、类型）"""
        # 获取所有不重复的学科
        subject_stmt = (
            select(TeachingResource.subject)
            .where(TeachingResource.status == "active")
            .distinct()
            .order_by(TeachingResource.subject)
        )
        subject_result = await self.db.execute(subject_stmt)
        subjects = [row[0] for row in subject_result.fetchall() if row[0]]

        # 获取所有不重复的年级
        grade_stmt = (
            select(TeachingResource.grade)
            .where(TeachingResource.status == "active")
            .distinct()
            .order_by(TeachingResource.grade)
        )
        grade_result = await self.db.execute(grade_stmt)
        grades = [row[0] for row in grade_result.fetchall() if row[0]]

        return {
            "subjects": subjects,
            "grades": grades,
            "resource_types": [
                {"value": k, "label": v} for k, v in RESOURCE_TYPE_LABELS.items()
            ],
            "file_types": [
                {"value": k, "label": v} for k, v in FILE_TYPE_LABELS.items()
            ],
        }
