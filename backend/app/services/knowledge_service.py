"""
知识图谱服务层 (PBI_11)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeService:
    """知识图谱业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: PBI_11 实现 — 图谱生成、节点查询、导出
