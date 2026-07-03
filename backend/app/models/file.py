"""文件管理 — SQLAlchemy 数据模型桩 (PBI_05)"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey

from app.core.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(16), nullable=False)
    file_size = Column(Integer, default=0)
    storage_path = Column(String(512), default="")
    parse_status = Column(String(16), default="pending")
    parsed_content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
