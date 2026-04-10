import asyncio
import inspect
import json
import os
import time
import uuid

import httpx
import pytest
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
    SESSION_REFRESH_TOKEN_KEY,
)
from ctao_shared.db import Base, encrypt_token, get_async_session, get_redis_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.tests.fakeredis import FakeRedis
from auth_service.models import UserTable

try:
    from starlette.testclient import LifespanManager
except Exception:
    from asgi_lifespan import LifespanManager


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(sessionmaker):
    async with sessionmaker() as s:
        yield s


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


def _make_asgi_transport(app) -> httpx.ASGITransport:
    # Compatible with httpx versions with/without lifespan kwarg
    params = inspect.signature(httpx.ASGITransport.__init__).parameters
    if "lifespan" in params:
        return httpx.ASGITransport(app=app, lifespan="off")
    return httpx.ASGITransport(app=app)


@pytest.fixture(scope="session")
def app():
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("ENV", "test")

    from auth_service.main import app as auth_app

    return auth_app


@pytest.fixture
async def auth_client(app, db_session, fake_redis):
    async def _override_db():
        yield db_session

    def _override_redis():
        return fake_redis

    app.dependency_overrides[get_async_session] = _override_db
    app.dependency_overrides[get_redis_client] = _override_redis

    async with LifespanManager(app):
        transport = _make_asgi_transport(app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def as_user(db_session, fake_redis, auth_client):
    async def _maker(
        email="u@example.org",
        first_name="Ada",
        last_name="Lovelace",
        iam_subject_id: str | None = None,
        access_token: str = "dummy-access-token",
        refresh_token_plain: str = "dummy-refresh-token",
        expires_in: int = 3600,
    ):
        sub = iam_subject_id or f"test-sub-{uuid.uuid4().hex[:8]}"

        res = await db_session.execute(select(UserTable).where(UserTable.iam_subject_id == sub))
        user = res.scalars().first()
        if not user:
            user = UserTable(iam_subject_id=sub, hashed_password="")
            db_session.add(user)
            await db_session.flush()

        session_id = str(uuid.uuid4())

        enc_rt = encrypt_token(refresh_token_plain)
        assert enc_rt is not None, "REFRESH_TOKEN_ENCRYPTION_KEY must be set for tests"

        session_payload = {
            "app_user_id": user.id,
            "iam_sub": sub,
            "iam_email": email,
            "first_name": first_name,
            "last_name": last_name,
            SESSION_ACCESS_TOKEN_KEY: access_token,
            SESSION_ACCESS_TOKEN_EXPIRY_KEY: time.time() + expires_in,
            SESSION_REFRESH_TOKEN_KEY: enc_rt,
        }
        await fake_redis.setex(
            f"{SESSION_KEY_PREFIX}{session_id}",
            8 * 3600,
            json.dumps(session_payload),
        )

        auth_client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)
        return user, session_id

    return _maker
