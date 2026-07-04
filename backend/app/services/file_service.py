"""
文件管理服务层 (PBI_05) — 文件上传、解析、状态查询、删除
"""

import csv
import io
import json
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import UploadedFile as UploadedFileModel
from app.schemas.file import ALLOWED_FILE_TYPES


# ------------------------------------------------------------------
# 自定义异常
# ------------------------------------------------------------------
class FileSizeExceededError(ValueError):
    """文件大小超限"""
    pass


class FileFormatError(ValueError):
    """文件格式不支持"""
    pass


class FileService:
    """文件上传 & 解析业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def upload(
        self,
        user_id: str,
        file: UploadFile,
        auto_parse: bool = True,
    ) -> UploadedFileModel:
        """
        上传文件：校验 → 存储 → 写 DB → 触发解析

        Args:
            user_id: 上传用户 ID
            file: FastAPI UploadFile 对象
            auto_parse: 是否自动触发解析

        Returns:
            UploadedFile 数据库对象

        Raises:
            ValueError: 文件格式不支持 / 文件大小超限
        """
        # 1. 校验
        file_type = self._extract_file_type(file.filename)
        if file_type not in ALLOWED_FILE_TYPES:
            raise FileFormatError(f"不支持的文件格式: .{file_type}")

        content = await file.read()
        file_size = len(content)

        if file_size > settings.max_file_size_bytes:
            raise FileSizeExceededError(
                f"文件大小 {file_size / 1024 / 1024:.1f}MB 超过上限 "
                f"{settings.MAX_FILE_SIZE_MB}MB"
            )

        # 2. 存储到磁盘
        storage_path = self._build_storage_path(user_id, file.filename)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(content)

        # 3. 写入数据库
        record = UploadedFileModel(
            user_id=user_id,
            filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            parse_status="pending",
        )
        self.db.add(record)
        await self.db.flush()

        # 4. 触发解析
        if auto_parse:
            await self._run_parse(record, content)

        logger.info(
            f"文件上传成功 | user={user_id} | file={file.filename} "
            f"| type={file_type} | size={file_size} | auto_parse={auto_parse}"
        )
        return record

    async def get_user_files(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页查询用户的文件列表"""
        # 总数
        count_stmt = select(func.count(UploadedFileModel.id)).where(
            UploadedFileModel.user_id == user_id
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 列表（按创建时间倒序）
        stmt = (
            select(UploadedFileModel)
            .where(UploadedFileModel.user_id == user_id)
            .order_by(desc(UploadedFileModel.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = [
            {
                "id": r.id,
                "filename": r.filename,
                "file_type": r.file_type,
                "file_size": r.file_size,
                "parse_status": r.parse_status,
                "created_at": r.created_at,
            }
            for r in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
        }

    async def get_file_status(self, file_id: str, user_id: str) -> dict | None:
        """查询单个文件的解析状态"""
        record = await self._get_owned_file(file_id, user_id)
        if not record:
            return None

        return {
            "file_id": record.id,
            "filename": record.filename,
            "file_type": record.file_type,
            "file_size": record.file_size,
            "parse_status": record.parse_status,
            "parsed_content": record.parsed_content,
            "summary": None,
            "knowledge_points": [],
        }

    async def reparse_file(self, file_id: str, user_id: str) -> UploadedFileModel | None:
        """重新解析文件"""
        record = await self._get_owned_file(file_id, user_id)
        if not record:
            return None

        # 读取磁盘文件
        try:
            with open(record.storage_path, "rb") as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"重新解析失败：文件不存在 | path={record.storage_path}")
            record.parse_status = "failed"
            await self.db.flush()
            return record

        await self._run_parse(record, content)
        logger.info(f"重新解析已触发 | file_id={file_id} | user={user_id}")
        return record

    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """删除文件（数据库记录 + 磁盘文件）"""
        record = await self._get_owned_file(file_id, user_id)
        if not record:
            return False

        # 删除磁盘文件
        try:
            if os.path.exists(record.storage_path):
                os.remove(record.storage_path)
        except OSError as e:
            logger.warning(f"删除磁盘文件失败 | path={record.storage_path} | error={e}")

        # 删除数据库记录
        await self.db.delete(record)
        await self.db.flush()

        logger.info(f"文件已删除 | file_id={file_id} | user={user_id}")
        return True

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_owned_file(self, file_id: str, user_id: str) -> UploadedFileModel | None:
        """获取属于指定用户的文件记录"""
        stmt = select(UploadedFileModel).where(
            UploadedFileModel.id == file_id,
            UploadedFileModel.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _run_parse(self, record: UploadedFileModel, content: bytes) -> None:
        """
        执行文件解析（同步，当前请求内完成）

        对于大文件或 PDF/DOCX 等复杂格式，后续可改为 Celery 异步任务。
        """
        record.parse_status = "processing"
        await self.db.flush()

        try:
            parsed = await self._parse_content(content, record.file_type)
            record.parsed_content = parsed
            record.parse_status = "done"
        except Exception as e:
            logger.error(f"文件解析失败 | file_id={record.id} | type={record.file_type} | error={e}")
            record.parsed_content = None
            record.parse_status = "failed"

        await self.db.flush()

    async def _parse_content(self, content: bytes, file_type: str) -> str:
        """
        按文件类型分发解析

        支持 9 种格式:
          - 纯文本类: txt, md, csv, json, html, xml, yaml
          - 二进制类: pdf, docx（需额外依赖，缺失时返回提示）
        """
        parsers = {
            "txt":  self._parse_text,
            "md":   self._parse_text,
            "csv":  self._parse_csv,
            "json": self._parse_json,
            "html": self._parse_text,
            "xml":  self._parse_text,
            "yaml": self._parse_text,
            "pdf":  self._parse_pdf,
            "docx": self._parse_docx,
        }

        parser = parsers.get(file_type, self._parse_text)
        return await parser(content)

    # --- 纯文本解析器 ---

    async def _parse_text(self, content: bytes) -> str:
        """通用文本解析（txt / md / html / xml / yaml）"""
        for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    async def _parse_csv(self, content: bytes) -> str:
        """CSV 解析 → 格式化文本"""
        text = await self._parse_text(content)
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return text
            # 格式化为可读文本
            lines = []
            for _, row in enumerate(rows):
                lines.append(" | ".join(row))
            return "\n".join(lines)
        except Exception:
            return text

    async def _parse_json(self, content: bytes) -> str:
        """JSON 解析 → 格式化文本"""
        text = await self._parse_text(content)
        try:
            data = json.loads(text)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return text

    # --- 二进制格式解析器 ---

    async def _parse_pdf(self, content: bytes) -> str:
        """
        PDF 解析

        优先使用 pdfplumber，其次 PyPDF2。
        均未安装时返回提示信息。
        """
        # 尝试 pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages) if pages else ""
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pdfplumber 解析异常: {e}")

        # 尝试 PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages) if pages else ""
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"PyPDF2 解析异常: {e}")

        # 依赖缺失
        logger.warning("PDF 解析失败：缺少 pdfplumber 或 PyPDF2 依赖")
        return "[PDF 解析需要安装依赖] 请运行: pip install pdfplumber 或 pip install PyPDF2"

    async def _parse_docx(self, content: bytes) -> str:
        """
        DOCX 解析

        使用 python-docx，未安装时返回提示。
        """
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            return "\n".join(paragraphs) if paragraphs else ""
        except ImportError:
            logger.warning("DOCX 解析失败：缺少 python-docx 依赖")
            return "[DOCX 解析需要安装依赖] 请运行: pip install python-docx"
        except Exception as e:
            logger.error(f"DOCX 解析异常: {e}")
            raise

    # --- 工具方法 ---

    @staticmethod
    def _extract_file_type(filename: str) -> str:
        """从文件名提取扩展名（小写，不含点）"""
        suffix = Path(filename).suffix.lstrip(".").lower()
        return suffix or "txt"

    @staticmethod
    def _build_storage_path(user_id: str, filename: str) -> str:
        """构建文件存储路径: UPLOAD_DIR/{user_id}/{uuid}_{filename}"""
        safe_name = Path(filename).name  # 防路径穿越
        unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
        return os.path.join(settings.UPLOAD_DIR, user_id, unique_name)
