"""
测试配置 & 全局 Fixtures

测试环境使用 SQLite 内存数据库，无需 MySQL。
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# 测试环境强制使用 SQLite，避免依赖外部 MySQL
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.database import Base
from app.main import app

# 测试数据库 URL（使用 SQLite 进行单元测试）
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环（整个测试 session 共享）"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """每次测试前重建数据库表"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """提供测试数据库会话"""
    async with TestSessionLocal() as session:
        yield session


async def override_get_db():
    """测试用数据库会话 — 替代 MySQL 连接"""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """提供异步 HTTP 测试客户端（已注入 SQLite 数据库依赖）"""
    # 覆盖 FastAPI 的 get_db 依赖，使用 SQLite 测试库
    app.dependency_overrides[deps.get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    # 清理覆盖
    app.dependency_overrides.clear()
