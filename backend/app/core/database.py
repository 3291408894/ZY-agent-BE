"""
数据库引擎 & 会话管理 — SQLAlchemy 2.0 异步
支持 SQLite / MySQL
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 根据数据库类型配置引擎参数
if "sqlite" in settings.DATABASE_URL:
    # SQLite: 需要 check_same_thread=False, 启用外键
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    # MySQL: 使用连接池，aiomysql 下必须关闭 pool_pre_ping
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=False,
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
