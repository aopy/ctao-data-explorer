from __future__ import annotations

import logging

import redis.asyncio as redis

from api.config import get_api_settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def get_api_redis_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        s = get_api_settings()
        url = (s.API_REDIS_URL or "").strip()
        if not url:
            logger.warning("API_REDIS_URL not set; Redis caching disabled.")
            url = "redis://localhost:6379/1"
        _pool = redis.ConnectionPool.from_url(url)
    return _pool


async def close_redis() -> None:
    """Dispose the shared Redis pool if we created one."""
    global _pool
    if _pool is None:
        return
    try:
        await _pool.disconnect(inuse_connections=True)
    finally:
        _pool = None
