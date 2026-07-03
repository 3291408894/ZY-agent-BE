"""
上传文件模型 (PBI_05)
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))  # pdf / docx / txt / md / csv / json / html / xml / yaml
    file_size: Mapped[int] = mapped_column(BigInteger)  # 字节数
    storage_path: Mapped[str] = mapped_column(String(512))
    parse_status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending / processing / done / failed
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(back_populates="uploaded_files")
