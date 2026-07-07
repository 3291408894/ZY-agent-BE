"""
Redis 连接管理
"""

import redis.asyncio as aioredis

from app.core.config import settings

# 全局 Redis 连接池（惰性初始化）
_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接（单例）"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
