"""
AI Agent 服务层 (PBI_04, PBI_12) — 会话管理、消息存储、流式对话
"""

from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class AgentService:
    """Agent 对话业务逻辑"""

    # 自动标题：截取用户首条消息的前 N 个字符
    AUTO_TITLE_MAX_LEN = 30

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    async def create_session(self, user_id: str) -> ChatSession:
        """创建新会话"""
        session = ChatSession(user_id=user_id, title="新对话")
        self.db.add(session)
        await self.db.flush()
        logger.info(f"会话已创建 | session_id={session.id} | user={user_id}")
        return session

    async def get_sessions(self, user_id: str) -> list[dict]:
        """
        获取用户的会话列表，按日期分组（仿 DeepSeek 网页版）

        返回:
            [
                {"label": "今天", "sessions": [...]},
                {"label": "昨天", "sessions": [...]},
                {"label": "本周", "sessions": [...]},
                {"label": "更早", "sessions": [...]},
            ]
        """
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)

        groups: dict[str, list] = {
            "今天": [],
            "昨天": [],
            "本周": [],
            "更早": [],
        }

        for s in rows:
            created = s.created_at.replace(tzinfo=timezone.utc) if s.created_at.tzinfo is None else s.created_at
            item = {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            if created >= today_start:
                groups["今天"].append(item)
            elif created >= yesterday_start:
                groups["昨天"].append(item)
            elif created >= week_start:
                groups["本周"].append(item)
            else:
                groups["更早"].append(item)

        # 只返回非空分组
        return [
            {"label": label, "sessions": sessions}
            for label, sessions in groups.items()
            if sessions
        ]

    async def get_session_detail(self, session_id: str, user_id: str) -> dict | None:
        """获取会话详情（含消息列表）"""
        stmt = (
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            return None

        # 加载消息（按时间正序）
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = (await self.db.execute(msg_stmt)).scalars().all()

        return {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": m.content,
                    "thought_chain": m.thought_chain,
                    "tool_calls": m.tool_calls,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }

    async def update_session_title(
        self, session_id: str, user_id: str, title: str
    ) -> ChatSession | None:
        """修改会话标题（用户自定义）"""
        session = await self._get_owned_session(session_id, user_id)
        if not session:
            return None
        session.title = title.strip()
        await self.db.flush()
        logger.info(f"会话标题已更新 | session_id={session_id} | title={title}")
        return session

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """删除会话（级联删除所有消息）"""
        session = await self._get_owned_session(session_id, user_id)
        if not session:
            return False
        await self.db.delete(session)
        await self.db.flush()
        logger.info(f"会话已删除 | session_id={session_id} | user={user_id}")
        return True

    # ------------------------------------------------------------------
    # 消息
    # ------------------------------------------------------------------

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        thought_chain: list | None = None,
        tool_calls: list | None = None,
    ) -> ChatMessage:
        """保存一条消息到数据库"""
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
            session.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return msg

    async def _auto_title(self, session_id: str) -> None:
        """
        自动生成会话标题：取首条用户消息前 N 个字符
        仅当标题仍为"新对话"时触发
        """
        session = await self.db.get(ChatSession, session_id)
        if not session or session.title != "新对话":
            return

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        first_msg = result.scalar_one_or_none()

        if first_msg:
            raw = first_msg.content.strip().replace("\n", " ")
            title = raw[: self.AUTO_TITLE_MAX_LEN]
            if len(raw) > self.AUTO_TITLE_MAX_LEN:
                title += "…"
            session.title = title or "新对话"
            await self.db.flush()
            logger.info(f"自动标题已生成 | session_id={session_id} | title={session.title}")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    async def _get_owned_session(self, session_id: str, user_id: str) -> ChatSession | None:
        """获取属于指定用户的会话"""
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
