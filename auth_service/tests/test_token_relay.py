import json
import time

import pytest
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    COOKIE_NAME_XSRF,
    HEADER_NAME_XSRF,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from auth_service.config import get_auth_settings
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
    get_auth_settings.cache_clear()
    relay_mod._settings.cache_clear()

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
    get_auth_settings.cache_clear()
    relay_mod._settings.cache_clear()

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


@pytest.mark.anyio
async def test_token_relay_forwards_xsrf_cookie_and_header(auth_client, as_user, monkeypatch):
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
                "xsrf_header": request.headers.get(HEADER_NAME_XSRF),
            }
        )

    relay_mod.register_asgi_target("xsrf-target", downstream)

    monkeypatch.setenv("TOKEN_RELAY_TARGETS_JSON", '{"xsrf-target":"asgi://xsrf-target"}')
    monkeypatch.setenv("TOKEN_RELAY_TIMEOUT_SECONDS", "5")
    get_auth_settings.cache_clear()
    relay_mod._settings.cache_clear()

    _, session_id = await as_user(access_token="AT-123", refresh_token_plain="RT-xyz")
    auth_client.cookies.set(COOKIE_NAME_MAIN_SESSION, session_id)

    xsrf_token = "csrf-token-123"
    auth_client.cookies.set(COOKIE_NAME_XSRF, xsrf_token)

    r = await auth_client.post(
        "/auth/xsrf-target/protected/mutation",
        headers={HEADER_NAME_XSRF: xsrf_token},
        json={"ok": True},
    )

    assert r.status_code == 200, r.text
    data = r.json()

    assert data["authorization"] == "Bearer AT-123"
    assert data["path"] == "/protected/mutation"
    assert data["xsrf_header"] == xsrf_token
    assert data["cookie"] == f"{COOKIE_NAME_XSRF}={xsrf_token}"
    assert COOKIE_NAME_MAIN_SESSION not in data["cookie"]
