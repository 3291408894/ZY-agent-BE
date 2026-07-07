"""
文件管理相关 Pydantic Schema (PBI_05)
"""

from datetime import datetime

from pydantic import BaseModel


class FileUploadResp(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    parse_status: str
    parsed_content: str | None = None
    created_at: datetime


class FileStatusResp(BaseModel):
    file_id: str
    parse_status: str
    parsed_content: str | None = None
    summary: str | None = None
    knowledge_points: list[str] = []


class FileItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    parse_status: str
    created_at: datetime
