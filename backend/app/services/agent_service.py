"""
AI Agent 服务层 (PBI_04, PBI_12)
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class AgentService:
    """Agent 对话业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_session(self, user_id: str, session_id: str | None = None, title: str = "新对话") -> ChatSession:
        """获取已有会话或创建新会话"""
        if session_id:
            session = await self.db.get(ChatSession, session_id)
            if session and session.user_id == user_id:
                return session
        # 创建新会话
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        await self.db.flush()
        return session

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        thought_chain: list | None = None,
        tool_calls: list | None = None,
    ) -> ChatMessage:
        """保存一条消息"""
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            thought_chain=thought_chain,
            tool_calls=tool_calls,
        )
        self.db.add(msg)
        # 更新会话时间
        session = await self.db.get(ChatSession, session_id)
        if session:
            # 自动用第一条用户消息作为标题
            if session.title == "新对话" and role == "user":
                session.title = content[:30] + ("..." if len(content) > 30 else "")
            self.db.add(session)
        await self.db.flush()
        return msg

    async def list_sessions(self, user_id: str) -> list[ChatSession]:
        """获取用户的会话列表（按更新时间倒序）"""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_messages(self, session_id: str, user_id: str) -> list[ChatMessage]:
        """获取会话的历史消息"""
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return []
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """删除会话及其所有消息"""
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return False
        await self.db.delete(session)
        await self.db.flush()
        return True

    async def update_session_title(self, session_id: str, title: str) -> None:
        """更新会话标题"""
        session = await self.db.get(ChatSession, session_id)
        if session:
            session.title = title
            self.db.add(session)
            await self.db.flush()
