"""
课文总结服务层 (PBI_06)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class SummaryService:
    """课文总结业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: PBI_06 实现 — 调用 LLM 生成总结、存储记录
