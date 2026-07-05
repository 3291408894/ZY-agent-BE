"""
Redis 连接管理（可选组件，不可用时不影响核心功能）
"""

import redis.asyncio as aioredis

from app.core.config import settings

# 全局 Redis 连接池（惰性初始化）
_redis_pool: aioredis.Redis | None = None
_redis_unavailable: bool = False


async def get_redis() -> aioredis.Redis | None:
    """获取 Redis 连接（单例），不可用时返回 None"""
    global _redis_pool, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            # 测试连接
            await _redis_pool.ping()
        except Exception:
            _redis_pool = None
            _redis_unavailable = True
            return None
    return _redis_pool


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.close()
        except Exception:
            pass
        _redis_pool = None
