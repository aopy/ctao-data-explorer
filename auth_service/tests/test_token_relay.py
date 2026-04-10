import json
import time

import pytest
from ctao_shared.config import get_settings
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
)
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


@pytest.mark.anyio
async def test_token_relay_no_access_token_is_distinguishable(
    auth_client, as_user, fake_redis, monkeypatch
):
    # Create and register a downstream ASGI app (needed for routing validity)
    downstream = FastAPI()

    @downstream.api_route(
        "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    async def echo(_request: Request, _path: str):
        return JSONResponse({"ok": True})

    relay_mod.register_asgi_target("whoami", downstream)

    # Point relay target to the ASGI app
    monkeypatch.setenv("TOKEN_RELAY_TARGETS_JSON", '{"whoami":"asgi://whoami"}')
    monkeypatch.setenv("TOKEN_RELAY_TIMEOUT_SECONDS", "5")
    from ctao_shared.config import get_settings

    get_settings.cache_clear()

    # Create session but remove access token
    _, session_id = await as_user(access_token="AT-123", refresh_token_plain="RT-xyz")

    raw = await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    assert raw is not None
    session = json.loads(raw)
    session[SESSION_ACCESS_TOKEN_KEY] = None
    session[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = time.time() + 3600
    await fake_redis.setex(f"{SESSION_KEY_PREFIX}{session_id}", 3600, json.dumps(session))

    auth_client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)

    r = await auth_client.get("/auth/whoami/test")
    assert r.status_code == 401

    data = r.json()
    assert data.get("detail") == "reauth_required"
    assert data.get("reason") == "no_access_token"

    wa = r.headers.get("www-authenticate", "")
    assert "reauth_required" in wa
