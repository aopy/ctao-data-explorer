from __future__ import annotations

import redis.asyncio as redis

from auth_service.config import get_auth_settings

_pool: redis.ConnectionPool | None = None


def get_redis_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        url = get_auth_settings().AUTH_REDIS_URL
        _pool = redis.ConnectionPool.from_url(url, decode_responses=True)
    return _pool


def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=get_redis_pool(), decode_responses=True)
