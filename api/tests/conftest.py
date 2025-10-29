import os
import inspect
import pytest
import httpx
from fastapi import FastAPI

try:
    from starlette.testclient import LifespanManager
except Exception:
    from asgi_lifespan import LifespanManager

@pytest.fixture(scope="session")
def anyio_backend():
    # Force AnyIO to use asyncio everywhere
    return "asyncio"

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
