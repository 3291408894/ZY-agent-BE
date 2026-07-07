"""
教学资源库 Schema — 上传请求、列表查询、响应、枚举 (功能3)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# 枚举
# ============================================================

class ResourceTypeEnum(str, Enum):
    COURSEWARE = "courseware"
    EXAM_PAPER = "exam_paper"
    LESSON_PLAN = "lesson_plan"
    OTHER = "other"


class ResourceVisibilityEnum(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class ResourceStatusEnum(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    REVIEWING = "reviewing"


# 允许的文件扩展名 → file_type 映射
EXT_TO_FILE_TYPE: dict[str, str] = {
    # 文档类
    "pdf": "pdf",
    "doc": "docx",
    "docx": "docx",
    # 演示类
    "ppt": "pptx",
    "pptx": "pptx",
    # 表格类
    "xls": "xlsx",
    "xlsx": "xlsx",
    # 媒体类
    "mp4": "mp4",
    "avi": "mp4",
    "mov": "mp4",
    "mp3": "mp3",
    "wav": "mp3",
    "flac": "mp3",
    # 图片类
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "gif": "image",
    "bmp": "image",
    "webp": "image",
    "svg": "image",
    # 文本类
    "txt": "txt",
    "md": "txt",
    # 压缩包
    "zip": "zip",
    "rar": "zip",
    "7z": "zip",
}

ALLOWED_EXTENSIONS = set(EXT_TO_FILE_TYPE.keys())

# file_type 显示标签
FILE_TYPE_LABELS: dict[str, str] = {
    "pdf": "PDF 文档",
    "docx": "Word 文档",
    "pptx": "PPT 课件",
    "xlsx": "Excel 表格",
    "mp4": "视频",
    "mp3": "音频",
    "image": "图片",
    "txt": "文本",
    "zip": "压缩包",
}

RESOURCE_TYPE_LABELS: dict[str, str] = {
    "courseware": "课件",
    "exam_paper": "试卷",
    "lesson_plan": "教案",
    "other": "其他",
}


# ============================================================
# 上传
# ============================================================

class ResourceUploadResp(BaseModel):
    """上传成功后返回的资源信息"""
    id: str
    uploader_id: str
    title: str
    description: str | None
    subject: str
    grade: str
    resource_type: str
    file_type: str
    file_name: str
    file_size: int
    file_ext: str
    visibility: str
    tags: list[str] | None
    created_at: datetime


# ============================================================
# 资源列表项 & 详情
# ============================================================

class ResourceUploaderBrief(BaseModel):
    """上传者简要信息"""
    id: str
    nickname: str
    avatar_url: str | None


class ResourceItem(BaseModel):
    """资源列表项"""
    id: str
    title: str
    description: str | None
    subject: str
    grade: str
    resource_type: str
    resource_type_label: str
    file_type: str
    file_type_label: str
    file_name: str
    file_size: int
    file_ext: str
    download_count: int
    view_count: int
    like_count: int
    visibility: str
    tags: list[str] | None
    is_favorited: bool = False
    uploader: ResourceUploaderBrief | None = None
    created_at: datetime


class ResourceDetail(BaseModel):
    """资源详情"""
    id: str
    title: str
    description: str | None
    subject: str
    grade: str
    resource_type: str
    resource_type_label: str
    file_type: str
    file_type_label: str
    file_name: str
    file_size: int
    file_ext: str
    download_count: int
    view_count: int
    like_count: int
    visibility: str
    tags: list[str] | None
    keywords: str | None
    status: str
    is_favorited: bool = False
    uploader: ResourceUploaderBrief | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================
# 列表查询参数
# ============================================================

class ResourceListParams(BaseModel):
    """资源列表查询参数"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = None
    subject: str | None = None
    grade: str | None = None
    resource_type: ResourceTypeEnum | None = None
    file_type: str | None = None
    sort_by: str = Field(default="created_at", description="created_at / download_count / like_count")
    sort_order: str = Field(default="desc", description="asc / desc")


# ============================================================
# 收藏
# ============================================================

class FavoriteStatus(BaseModel):
    """收藏状态"""
    is_favorited: bool
    resource_id: str
