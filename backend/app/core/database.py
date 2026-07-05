"""
数据库引擎 & 会话管理 — SQLAlchemy 2.0 异步
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=False,  # aiomysql 下必须关闭，否则 MissingGreenlet
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 声明式基类
class Base(DeclarativeBase):
    pass
