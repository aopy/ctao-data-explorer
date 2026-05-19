from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from pydantic import BaseModel

from api.metrics import cache_hit, cache_miss, observe_redis

logger = logging.getLogger(__name__)


def _cache_key_fingerprint(cache_key: object) -> str:
    return hashlib.sha256(str(cache_key).encode("utf-8")).hexdigest()[:12]


def build_cache_key_from_adql(adql_query_str: str) -> str:
    return "search:" + hashlib.sha256(adql_query_str.encode()).hexdigest()


async def redis_get_json_model[TModel: BaseModel](
    redis_client: Any,
    cache_key: str,
    model_cls: type[TModel],
    *,
    metric_name: str,
) -> TModel | None:
    t0 = time.perf_counter()
    ok = False

    try:
        cached = await redis_client.get(cache_key)
        ok = True
    except Exception:
        cached = None
        logger.warning(
            "Redis get failed for key_hash=%s",
            _cache_key_fingerprint(cache_key),
            exc_info=True,
        )
    finally:
        observe_redis("get", time.perf_counter() - t0, ok)

    if cached:
        cache_hit(metric_name)
        if isinstance(cached, bytes):
            cached = cached.decode()
        return model_cls.model_validate_json(cached)

    cache_miss(metric_name)
    return None


async def redis_set_json_model(
    redis_client: Any,
    cache_key: str,
    obj: BaseModel,
    ttl: int,
) -> None:
    t0 = time.perf_counter()
    ok = False

    try:
        await redis_client.set(cache_key, obj.model_dump_json(), ex=ttl)
        ok = True
    except Exception:
        logger.warning(
            "Redis set failed for key_hash=%s",
            _cache_key_fingerprint(cache_key),
            exc_info=True,
        )
    finally:
        observe_redis("set", time.perf_counter() - t0, ok)


async def redis_get_json_dict(
    redis_client: Any,
    cache_key: str,
    *,
    metric_name: str,
) -> dict[str, Any] | None:
    import json

    t0 = time.perf_counter()
    ok = False

    try:
        cached = await redis_client.get(cache_key)
        ok = True
    except Exception:
        cached = None
        logger.warning(
            "Redis get failed for key_hash=%s",
            _cache_key_fingerprint(cache_key),
            exc_info=True,
        )
    finally:
        observe_redis("get", time.perf_counter() - t0, ok)

    if cached:
        cache_hit(metric_name)
        if isinstance(cached, bytes):
            cached = cached.decode()
        return dict(json.loads(cached))

    cache_miss(metric_name)
    return None


async def redis_set_json_dict(
    redis_client: Any,
    cache_key: str,
    obj: dict[str, Any],
    ttl: int,
) -> None:
    import json

    t0 = time.perf_counter()
    ok = False

    try:
        await redis_client.set(cache_key, json.dumps(obj), ex=ttl)
        ok = True
    except Exception:
        logger.warning(
            "Redis set failed for key_hash=%s",
            _cache_key_fingerprint(cache_key),
            exc_info=True,
        )
    finally:
        observe_redis("set", time.perf_counter() - t0, ok)
