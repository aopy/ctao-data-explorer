import pytest
from ctao_shared.config import get_settings
from ctao_shared.constants import COOKIE_NAME_MAIN_SESSION
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from auth_service.routers import token_relay as relay_mod


@pytest.mark.anyio
async def test_token_relay_injects_bearer(auth_client, as_user, monkeypatch):
    downstream = FastAPI()

    @downstream.api_route(
        "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    async def echo(request: Request, path: str):
        return JSONResponse(
            {
                "path": "/" + path,
                "authorization": request.headers.get("authorization"),
                "cookie": request.headers.get("cookie"),
            }
        )

    relay_mod.register_asgi_target("whoami", downstream)

    monkeypatch.setenv("TOKEN_RELAY_TARGETS_JSON", '{"whoami":"asgi://whoami"}')
    monkeypatch.setenv("TOKEN_RELAY_TIMEOUT_SECONDS", "5")
    get_settings.cache_clear()

    # create session with access token
    _, session_id = await as_user(access_token="AT-123", refresh_token_plain="RT-xyz")
    auth_client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)

    r = await auth_client.get("/auth/whoami/test")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["authorization"] == "Bearer AT-123"
    assert data["cookie"] is None
    assert data["path"] == "/test"
