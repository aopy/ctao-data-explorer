import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from ctao_shared.config import get_settings
from ctao_shared.db import get_redis_pool
from ctao_shared.logging_config import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth_service.routers.auth import auth_api_router
from auth_service.routers.oidc import oidc_router

settings = get_settings()


def _init_redis_for_app(app: FastAPI) -> redis.ConnectionPool | None:
    pool = get_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool, decode_responses=True)
    return pool


async def _safe_close(obj: object) -> None:
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
    pool = _init_redis_for_app(app)
    try:
        yield
    finally:
        r = getattr(app.state, "redis", None)
        if r is not None:
            await _safe_close(r)
        if pool is not None:
            await _safe_close(pool)


setup_logging(
    level=settings.LOG_LEVEL,
    include_access=settings.LOG_INCLUDE_ACCESS,
    json=settings.LOG_JSON,
)

app = FastAPI(
    title="CTAO Auth Service",
    description="Central authentication & session service for CTAO applications",
    lifespan=lifespan,
)

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

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY_OIDC,
    session_cookie="ctao_oidc_state_session",
    https_only=False,
    max_age=600,
)

# auth service endpoints live under /api/*
app.include_router(oidc_router, prefix="/api")
app.include_router(auth_api_router, prefix="/api")
