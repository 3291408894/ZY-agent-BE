"""
AI Agent 服务层 (PBI_04, PBI_12)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class AgentService:
    """Agent 对话业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: PBI_04 实现 — 会话管理、消息存储、流式对话
