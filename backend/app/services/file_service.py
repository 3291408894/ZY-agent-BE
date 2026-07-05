"""
文件管理服务层 (PBI_05)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class FileService:
    """文件上传 & 解析业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: PBI_05 实现 — 文件上传、异步解析、状态查询
