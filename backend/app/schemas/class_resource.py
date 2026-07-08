"""
班级资源分享 Schema — 请求/响应模型
"""

from pydantic import BaseModel, Field


class SendToClassRequest(BaseModel):
    """发送资源到班级请求"""
    class_ids: list[str] = Field(..., min_length=1, description="目标班级ID列表")


class ClassResourceItem(BaseModel):
    """班级资源分享记录响应"""
    id: str
    class_id: str
    class_name: str = ""
    resource_id: str
    resource_title: str = ""
    resource_file_type: str = ""
    resource_file_name: str = ""
    resource_file_size: int = 0
    resource_subject: str = ""
    resource_grade: str = ""
    shared_by: str
    shared_by_name: str = ""
    created_at: str | None = None

    class Config:
        from_attributes = True
