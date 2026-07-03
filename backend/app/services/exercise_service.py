"""
习题服务层 (PBI_08, PBI_09, PBI_10)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ExerciseService:
    """习题业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: PBI_08/09/10 实现 — 生成习题、批改、历史记录
