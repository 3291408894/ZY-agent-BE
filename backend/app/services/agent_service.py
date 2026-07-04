"""
AI Agent 服务层 (PBI_04, PBI_12)

负责:
- 会话管理（创建、列表、详情、删除）
- 消息存储（用户消息 + AI 回复 + 思考链）
- 编排器调用与 SSE 事件流
- 会话标题自动生成
"""

<<<<<<< HEAD
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

=======
import uuid
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.orchestrator import agent_orchestrator
>>>>>>> main
from app.models.chat import ChatMessage, ChatSession


class AgentService:
    """Agent 对话业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

<<<<<<< HEAD
    async def get_or_create_session(
        self, user_id: str, session_id: str | None = None, title: str = "新对话"
    ) -> ChatSession:
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

    async def list_sessions(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[ChatSession], int]:
        """获取用户的会话列表（按更新时间倒序，分页）"""
=======
    # ================================================================
    # 会话管理
    # ================================================================

    async def get_or_create_session(
        self, user_id: str, session_id: str | None, first_message: str
    ) -> ChatSession:
        """
        获取已有会话或创建新会话。

        参数:
            user_id: 用户 ID
            session_id: 会话 ID（为 None 时创建新会话）
            first_message: 首条消息（用于自动生成标题）
        """
        if session_id:
            session = await self.db.get(ChatSession, session_id)
            if session and session.user_id == user_id:
                session.updated_at = func.now()
                await self.db.flush()
                return session

        # 创建新会话，自动截取标题
        title = first_message[:30] + ("..." if len(first_message) > 30 else "")
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
        )
        self.db.add(session)
        await self.db.flush()
        logger.info(f"[Agent] 创建新会话 | session_id={session.id} | user={user_id}")
        return session

    async def list_sessions(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[ChatSession], int]:
        """
        获取用户会话列表（分页，按更新时间倒序）。

        返回: (会话列表, 总数)
        """
>>>>>>> main
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == user_id)
        )
<<<<<<< HEAD
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 分页查询
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
=======
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 列表
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
>>>>>>> main
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        sessions = list(result.scalars().all())
<<<<<<< HEAD
        return sessions, total

    async def get_messages(self, session_id: str, user_id: str) -> list[ChatMessage]:
        """获取会话的历史消息"""
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return []
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
=======

        return sessions, total

    async def get_session_messages(
        self, user_id: str, session_id: str
    ) -> list[ChatMessage] | None:
        """
        获取会话的所有历史消息。

        返回: 消息列表，或 None（会话不存在或无权访问）
        """
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return None

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
>>>>>>> main
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

<<<<<<< HEAD
    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """删除会话及其所有消息"""
=======
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        删除会话（级联删除消息）。

        返回: True 成功，False 会话不存在或无权操作
        """
>>>>>>> main
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return False
        await self.db.delete(session)
        await self.db.flush()
<<<<<<< HEAD
        return True

    async def update_session_title(self, session_id: str, title: str) -> None:
        """更新会话标题"""
        session = await self.db.get(ChatSession, session_id)
        if session:
            session.title = title
            self.db.add(session)
            await self.db.flush()
=======
        logger.info(f"[Agent] 删除会话 | session_id={session_id}")
        return True

    # ================================================================
    # 消息存储
    # ================================================================

    async def save_user_message(self, session_id: str, content: str) -> ChatMessage:
        """保存用户消息"""
        msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def save_assistant_message(
        self,
        session_id: str,
        content: str,
        thought_chain: list[dict] | None = None,
        tool_calls: list[dict] | None = None,
    ) -> ChatMessage:
        """保存 AI 回复消息（含思考链和工具调用记录）"""
        msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            thought_chain=thought_chain,
            tool_calls=tool_calls,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    # ================================================================
    # SSE 流式对话
    # ================================================================

    async def chat_stream(
        self,
        user_id: str,
        session_id: str | None,
        message: str,
    ) -> AsyncIterator[dict]:
        """
        流式对话主流程 — 生成 SSE 事件流。

        流程:
        1. 获取/创建会话
        2. 保存用户消息
        3. 加载历史消息（最近 20 条）
        4. 调用编排器生成 SSE 事件流
        5. 从 done 事件中提取完整回复并保存 AI 消息

        参数:
            user_id: 当前用户 ID
            session_id: 会话 ID（None 则新建）
            message: 用户输入的消息

        Yields:
            SSE 事件字典
        """
        # 1. 获取/创建会话
        session = await self.get_or_create_session(user_id, session_id, message)
        actual_session_id = session.id

        # 2. 保存用户消息
        await self.save_user_message(actual_session_id, message)

        # 3. 加载历史消息（最近 20 条，用于上下文）
        history_messages = await self._load_history(actual_session_id, limit=20)

        # 4. 调用编排器流式生成
        full_response = ""
        thought_chain = None
        tool_calls = None
        has_error = False

        try:
            async for event in agent_orchestrator.run_stream(
                user_message=message,
                history=history_messages,
            ):
                # 注入 session_id 到 done 事件
                if event["type"] == "done":
                    event["session_id"] = actual_session_id
                    full_response = event.pop("full_response", "")
                    thought_chain = event.get("thought_chain")
                    tool_calls = event.get("tool_calls")
                elif event["type"] == "error":
                    has_error = True

                yield event

        except Exception as e:
            logger.error(f"[Agent] 流式对话异常 | session={actual_session_id} | error={e}")
            has_error = True
            yield {
                "type": "error",
                "message": f"对话处理异常: {str(e)}",
            }

        # 5. 保存 AI 回复消息
        if full_response and not has_error:
            await self.save_assistant_message(
                session_id=actual_session_id,
                content=full_response,
                thought_chain=thought_chain,
                tool_calls=tool_calls,
            )

    async def _load_history(
        self, session_id: str, limit: int = 20
    ) -> list[dict]:
        """
        加载会话历史消息，转换为 LLM 可用的格式。

        返回: [{"role": "user/assistant", "content": "..."}, ...]
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # 按时间正序

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    # ================================================================
    # 会话标题更新
    # ================================================================

    async def auto_update_title(self, session_id: str) -> None:
        """
        根据对话内容自动更新会话标题。
        取第一条用户消息的前 30 个字符作为标题。
        """
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        first_msg = result.scalar_one_or_none()
        if first_msg:
            session = await self.db.get(ChatSession, session_id)
            if session:
                title = first_msg.content[:30]
                if len(first_msg.content) > 30:
                    title += "..."
                session.title = title
                await self.db.flush()
>>>>>>> main
