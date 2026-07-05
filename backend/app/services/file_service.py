"""
文件管理服务层 (PBI_05)
"""

import os
import uuid
from pathlib import Path

import aiofiles
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import UploadedFile

# 支持的文件格式
ALLOWED_EXTENSIONS = {
    "txt", "md", "pdf", "docx", "csv", "json", "html", "xml", "yaml", "yml",
}
# 文本格式（可直接读取）
TEXT_EXTENSIONS = {"txt", "md", "csv", "json", "html", "xml", "yaml", "yml"}


class FileService:
    """文件上传 & 解析业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 上传 ─────────────────────────────────────────────

    async def upload(
        self, user_id: str, filename: str, content: bytes
    ) -> UploadedFile:
        """上传文件并保存到磁盘"""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: .{ext}")

        file_id = str(uuid.uuid4())
        # 按用户分目录
        user_dir = Path(settings.UPLOAD_DIR) / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_path = str(user_dir / f"{file_id}.{ext}")

        # 写入磁盘
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(content)

        record = UploadedFile(
            id=file_id,
            user_id=user_id,
            filename=filename,
            file_type=ext,
            file_size=len(content),
            storage_path=storage_path,
            parse_status="pending",
        )
        self.db.add(record)
        await self.db.flush()
        return record

    # ── 解析 ─────────────────────────────────────────────

    async def parse_file(self, file_id: str) -> str:
        """解析文件内容（同步执行，由调用方管理事务）"""
        record = await self.db.get(UploadedFile, file_id)
        if not record:
            raise ValueError("文件不存在")

        record.parse_status = "processing"
        self.db.add(record)
        await self.db.flush()

        try:
            ext = record.file_type
            if ext in TEXT_EXTENSIONS:
                # 文本格式直接读取
                async with aiofiles.open(record.storage_path, "r", encoding="utf-8") as f:
                    content = await f.read()
            elif ext == "pdf":
                content = await self._parse_pdf(record.storage_path)
            elif ext == "docx":
                content = await self._parse_docx(record.storage_path)
            else:
                content = f"[不支持解析的格式: {ext}]"

            record.parse_status = "done"
            record.parsed_content = content
            self.db.add(record)
            await self.db.flush()
            logger.info(f"文件解析成功: {record.filename} ({len(content)} 字符)")
            return content

        except Exception as e:
            record.parse_status = "failed"
            self.db.add(record)
            await self.db.flush()
            logger.error(f"文件解析失败: {record.filename} - {e}")
            raise

    async def _parse_pdf(self, path: str) -> str:
        """解析 PDF 文件（可选依赖）"""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
        except ImportError:
            raise RuntimeError("PDF 解析需要安装 PyPDF2: pip install PyPDF2")

    async def _parse_docx(self, path: str) -> str:
        """解析 DOCX 文件（可选依赖）"""
        try:
            from docx import Document

            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("DOCX 解析需要安装 python-docx: pip install python-docx")

    # ── 查询 ─────────────────────────────────────────────

    async def get_file(self, file_id: str, user_id: str) -> UploadedFile | None:
        """获取单个文件记录（带用户校验）"""
        record = await self.db.get(UploadedFile, file_id)
        if record and record.user_id == user_id:
            return record
        return None

    async def list_files(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        file_type: str | None = None,
    ) -> tuple[list[UploadedFile], int]:
        """获取用户的文件列表（按时间倒序，可分页和筛选）"""
        conditions = [UploadedFile.user_id == user_id]
        if file_type:
            conditions.append(UploadedFile.file_type == file_type)

        # 总数
        count_stmt = select(func.count()).select_from(UploadedFile).where(*conditions)
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 列表
        stmt = (
            select(UploadedFile)
            .where(*conditions)
            .order_by(UploadedFile.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # ── 删除 ─────────────────────────────────────────────

    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """删除文件记录及磁盘文件"""
        record = await self.db.get(UploadedFile, file_id)
        if not record or record.user_id != user_id:
            return False
        # 删除磁盘文件
        try:
            if os.path.exists(record.storage_path):
                os.remove(record.storage_path)
        except OSError:
            pass
        await self.db.delete(record)
        await self.db.flush()
        return True

    # ── 重新解析 ─────────────────────────────────────────

    async def reparse(self, file_id: str, user_id: str) -> UploadedFile | None:
        """重新触发文件解析"""
        record = await self.db.get(UploadedFile, file_id)
        if not record or record.user_id != user_id:
            return None
        await self.parse_file(file_id)
        return record
