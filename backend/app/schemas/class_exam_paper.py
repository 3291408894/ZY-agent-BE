"""
班级试卷分享 Schema
"""

from pydantic import BaseModel, Field


class SendExamPaperToClassRequest(BaseModel):
    """发送试卷到班级的请求"""
    class_ids: list[str] = Field(..., min_length=1, description="目标班级ID列表")


class ClassExamPaperItem(BaseModel):
    """班级试卷列表项"""
    id: str
    class_id: str
    class_name: str = ""
    exam_paper_id: str
    title: str = ""
    subject: str = ""
    grade: str = ""
    exam_type: str = ""
    total_score: int = 0
    resource_type: str = "exam_paper"
    shared_by: str
    shared_by_name: str = ""
    assignment_id: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True
