"""
文件管理相关 Pydantic Schema (PBI_05)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 允许的文件类型
# ============================================================
ALLOWED_FILE_TYPES: set[str] = {
    "txt", "md", "pdf", "docx", "csv", "json", "html", "xml", "yaml",
}


# ============================================================
# 请求
# ============================================================
class FileReparseReq(BaseModel):
    """重新解析请求（预留扩展，如指定解析模式）"""
    pass


# ============================================================
# 响应
# ============================================================
class FileUploadResp(BaseModel):
    """文件上传成功响应"""
    file_id: str
    filename: str
    file_size: int
    file_type: str
    parse_status: str
    created_at: datetime


class FileStatusResp(BaseModel):
    """文件解析状态响应"""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    parse_status: str  # pending / processing / done / failed
    parsed_content: str | None = None
    summary: str | None = None
    knowledge_points: list[str] = []


class FileItem(BaseModel):
    """文件列表项"""
    id: str
    filename: str
    file_type: str
    file_size: int
    parse_status: str
    created_at: datetime

    class Config:
        from_attributes = True
