import asyncio
import inspect
import json
import os
import time
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from auth_service.db_base import Base as AuthBase
from auth_service.models import UserTable
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_KEY_PREFIX,
    SESSION_USER_ID_KEY,
)
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from api.auth.deps import get_required_identity
from api.auth.deps_optional import get_optional_identity
from api.auth.jwt_verifier import VerifiedIdentity
from api.db import get_async_session
from api.db_base import Base as ApiBase
from api.tests.fakeredis import FakeRedis

try:
    from starlette.testclient import LifespanManager
except Exception:
    from asgi_lifespan import LifespanManager

TEST_EMAIL = "u@example.org"
TEST_GIVEN_NAME = "Ada"
TEST_FAMILY_NAME = "Lovelace"
TEST_NAME = "Ada Lovelace"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine() -> AsyncEngine:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
        echo=False,
    )

    import auth_service.models  # noqa: F401

    import api.models  # noqa: F401

    async def _init() -> None:
        async with eng.begin() as conn:
            await conn.run_sync(ApiBase.metadata.create_all)
            await conn.run_sync(AuthBase.metadata.create_all)

    asyncio.run(_init())
    yield eng
    asyncio.run(eng.dispose())


@pytest.fixture(scope="session")
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as s:
        yield s


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(scope="session")
def app() -> FastAPI:
    # Flags before importing app
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("ENV", "test")

    from api.main import app as fastapi_app

    return fastapi_app


def _make_asgi_transport(app: FastAPI) -> httpx.ASGITransport:
    params = inspect.signature(httpx.ASGITransport.__init__).parameters
    if "lifespan" in params:
        return httpx.ASGITransport(app=app, lifespan="off")
    return httpx.ASGITransport(app=app)


@pytest.fixture
async def client(app: FastAPI):
    async with LifespanManager(app):
        transport = _make_asgi_transport(app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://testserver",
            timeout=10.0,
        ) as ac:
            yield ac


# Override API DB dependency (API uses DB dependency injection)
@pytest.fixture(autouse=True)
def _override_api_db_dep(sessionmaker, app: FastAPI):
    async def _get_async_session_override():
        async with sessionmaker() as s:
            yield s

    app.dependency_overrides[get_async_session] = _get_async_session_override
    yield
    app.dependency_overrides.pop(get_async_session, None)


# API auth helpers (Bearer/JWT bypass)


@pytest.fixture
def force_api_identity(app: FastAPI):
    """
    Force API required auth to succeed without real JWT/JWKS.
    """
    ident = VerifiedIdentity(
        sub=f"sub-test-{uuid.uuid4().hex[:6]}",
        email=TEST_EMAIL,
        preferred_username=None,
        given_name=TEST_GIVEN_NAME,
        family_name=TEST_FAMILY_NAME,
        name=TEST_NAME,
        claims={},
    )
    app.dependency_overrides[get_required_identity] = lambda: ident
    yield ident
    app.dependency_overrides.pop(get_required_identity, None)


@pytest.fixture
def force_api_optional_identity(app: FastAPI):
    """
    Force API optional auth to return an identity (optional features like history writing run).
    """
    ident = VerifiedIdentity(
        sub=f"sub-test-{uuid.uuid4().hex[:6]}",
        email=TEST_EMAIL,
        preferred_username=None,
        given_name=TEST_GIVEN_NAME,
        family_name=TEST_FAMILY_NAME,
        name=TEST_NAME,
        claims={},
    )
    app.dependency_overrides[get_optional_identity] = lambda: ident
    yield ident
    app.dependency_overrides.pop(get_optional_identity, None)


# auth_service client + helper for session-cookie tests


@pytest.fixture
async def auth_client(db_session, fake_redis):
    from auth_service.main import app as auth_app  # lazy import
    from auth_service.redis_client import get_redis_client

    async def _override_db():
        yield db_session

    def _override_redis():
        return fake_redis

    auth_app.dependency_overrides[get_async_session] = _override_db
    auth_app.dependency_overrides[get_redis_client] = _override_redis

    def _make_asgi_transport_for(app: FastAPI) -> httpx.ASGITransport:
        params = inspect.signature(httpx.ASGITransport.__init__).parameters
        if "lifespan" in params:
            return httpx.ASGITransport(app=app, lifespan="on")
        return httpx.ASGITransport(app=app)

    transport = _make_asgi_transport_for(auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield client

    auth_app.dependency_overrides.clear()


@pytest.fixture
def as_user(db_session, fake_redis, client):
    """
    Create an auth_service session in FakeRedis and set the session cookie
    on the API test client (used by auth_service tests, not by API bearer auth).
    """

    async def _maker(
        email: str = TEST_EMAIL,
        first_name: str = TEST_GIVEN_NAME,
        last_name: str = TEST_FAMILY_NAME,
        iam_subject_id: str | None = None,
    ):
        sub = iam_subject_id or f"test-sub-{uuid.uuid4().hex[:8]}"

        res = await db_session.execute(select(UserTable).where(UserTable.iam_subject_id == sub))
        user = res.scalars().first()
        if not user:
            user = UserTable(iam_subject_id=sub, hashed_password="")
            db_session.add(user)
            await db_session.flush()

        session_id = str(uuid.uuid4())
        session_payload = {
            SESSION_USER_ID_KEY: user.id,
            SESSION_IAM_SUB_KEY: sub,
            SESSION_IAM_EMAIL_KEY: email,
            SESSION_IAM_GIVEN_NAME_KEY: first_name,
            SESSION_IAM_FAMILY_NAME_KEY: last_name,
            SESSION_ACCESS_TOKEN_KEY: "dummy",
            SESSION_ACCESS_TOKEN_EXPIRY_KEY: time.time() + 3600,
        }
        await fake_redis.setex(
            f"{SESSION_KEY_PREFIX}{session_id}", 8 * 3600, json.dumps(session_payload)
        )

        client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)
        return user, session_id

    return _maker
