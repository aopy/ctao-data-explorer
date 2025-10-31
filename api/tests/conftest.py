import asyncio
import os
import inspect
import pytest
import httpx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from api.db import Base, get_async_session, get_redis_client
from api.models import UserTable
from sqlalchemy import select
from api.tests.fakeredis import FakeRedis
from api.constants import (
    COOKIE_NAME_MAIN_SESSION, SESSION_KEY_PREFIX,
    SESSION_ACCESS_TOKEN_KEY, SESSION_ACCESS_TOKEN_EXPIRY_KEY,
)
import uuid
import json, time


try:
    from starlette.testclient import LifespanManager
except Exception:
    from asgi_lifespan import LifespanManager

@pytest.fixture(scope="session")
def anyio_backend():
    # Force AnyIO to use asyncio everywhere
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

# Override app deps to use test DB + FakeRedis
@pytest.fixture(autouse=True)
def _override_app_deps(fake_redis, sessionmaker, app):
    async def _get_async_session():
        async with sessionmaker() as s:
            yield s

    async def _get_redis_client():
        return fake_redis

    app.dependency_overrides[get_async_session] = _get_async_session
    app.dependency_overrides[get_redis_client] = _get_redis_client
    yield
    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_redis_client, None)

@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://testserver") as c:
        yield c

# Helper to inject a logged-in user
@pytest.fixture
def as_user(db_session, fake_redis, client):
    async def _maker(
        email="u@example.org",
        first_name="Ada",
        last_name="Lovelace",
        iam_subject_id: str | None = None,
    ):
        sub = iam_subject_id or f"test-sub-{uuid.uuid4().hex[:8]}"

        # Reuse if exists, else create
        res = await db_session.execute(select(UserTable).where(UserTable.iam_subject_id == sub))
        user = res.scalars().first()
        if not user:
            user = UserTable(iam_subject_id=sub, hashed_password="")
            db_session.add(user)
            await db_session.flush()

        # create a server-side session in fake_redis
        session_id = str(uuid.uuid4())
        session_payload = {
            "app_user_id": user.id,
            "iam_subject_id": sub,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            SESSION_ACCESS_TOKEN_KEY: "dummy",
            SESSION_ACCESS_TOKEN_EXPIRY_KEY: time.time() + 3600,
        }
        await fake_redis.setex(f"{SESSION_KEY_PREFIX}{session_id}", 8 * 3600, json.dumps(session_payload))

        # set browser cookie
        client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)
        return user
    return _maker


@pytest.fixture(scope="session")
def app() -> FastAPI:
    # Set test flags before importing the app
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("ENV", "test")

    from api.main import app as fastapi_app
    return fastapi_app


def _make_asgi_transport(app: FastAPI) -> httpx.ASGITransport:
    # Be compatible with httpx versions with/without the `lifespan`
    params = inspect.signature(httpx.ASGITransport.__init__).parameters
    if "lifespan" in params:
        return httpx.ASGITransport(app=app, lifespan="off")
    return httpx.ASGITransport(app=app)


@pytest.fixture
async def client(app: FastAPI):
    # Explicitly run startup/shutdown so background resources are ready
    async with LifespanManager(app):
        transport = _make_asgi_transport(app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=10.0,
        ) as ac:
            yield ac
