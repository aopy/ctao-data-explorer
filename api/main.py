from __future__ import annotations

import inspect
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
from typing import Any

import redis.asyncio as redis
from ctao_shared.logging_config import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from api.basket import basket_router
from api.config import get_api_settings
from api.coords import coord_router
from api.db import close_engine
from api.metrics import setup_metrics
from api.opus import router as opus_router
from api.query_history import query_history_router
from api.redis_client import close_redis, get_api_redis_pool
from api.routers.datalink import router as datalink_router
from api.routers.health import router as health_router
from api.routers.object_lookup import router as object_lookup_router
from api.routers.search import router as search_router
from api.routers.time import router as time_router


@lru_cache
def _settings() -> Any:
    return get_api_settings()


setup_logging(
    level=_settings().LOG_LEVEL,
    include_access=_settings().LOG_INCLUDE_ACCESS,
    json=_settings().LOG_JSON,
)

logger = logging.getLogger(__name__)


def _is_testing_env() -> bool:
    v = os.getenv("TESTING", "")
    return v.lower() in {"1", "true", "yes", "on"} or "PYTEST_CURRENT_TEST" in os.environ


def _init_redis_for_app(app: FastAPI) -> redis.ConnectionPool | None:
    if _is_testing_env():
        from api.tests.fakeredis import FakeRedis

        app.state.redis = FakeRedis()
        logger.info("Using in-memory FakeRedis for tests.")
        return None

    pool = get_api_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool, decode_responses=True)
    logger.info("Redis pool initialised.")
    return pool


async def _safe_close(obj: Any) -> None:
    """Call aclose/close/disconnect if present; await if needed; ignore RuntimeError on shutdown."""
    close = (
        getattr(obj, "aclose", None)
        or getattr(obj, "close", None)
        or getattr(obj, "disconnect", None)
    )
    if not close:
        return

    with suppress(RuntimeError):
        res = close()
        if inspect.isawaitable(res):
            await res


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("API starting up")
    pool = _init_redis_for_app(app)

    try:
        yield
    finally:
        r = getattr(app.state, "redis", None)
        if r is not None:
            await _safe_close(r)

        if pool is not None:
            await _safe_close(pool)

        await close_redis()
        await close_engine()
        logger.info("API resources closed.")


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> FastAPI:
    docs_enabled = _settings().ENABLE_DOCS

    app = FastAPI(
        title="CTAO Data Explorer API",
        description="An API to access and analyse high-energy astrophysics data from CTAO",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    setup_metrics(app)

    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(time_router)
    app.include_router(search_router)
    app.include_router(object_lookup_router)
    app.include_router(datalink_router)

    app.include_router(basket_router)
    app.include_router(opus_router)
    app.include_router(query_history_router)
    app.include_router(coord_router)

    serve_frontend = _env_truthy("SERVE_FRONTEND", "0")
    static_dir = os.getenv("STATIC_DIR", "./js/build")

    if serve_frontend:
        if os.path.isdir(static_dir):
            logger.info(
                "SERVE_FRONTEND enabled: mounting static SPA from '%s' at '/'.",
                static_dir,
            )
            app.mount("/", StaticFiles(directory=static_dir, html=True), name="js")
        else:
            logger.warning(
                "SERVE_FRONTEND enabled but static build dir '%s' not found; not mounting SPA.",
                static_dir,
            )

            @app.get("/", include_in_schema=False)
            def root() -> dict[str, str]:
                return {"status": "ok", "app": "CTAO Data Explorer API"}

    else:

        @app.get("/", include_in_schema=False)
        def root() -> dict[str, str]:
            return {"status": "ok", "app": "CTAO Data Explorer API"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
