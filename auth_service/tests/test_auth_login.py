import json
import time
from unittest.mock import patch

import pytest
from ctao_shared.config import get_settings
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    COOKIE_NAME_XSRF,
    HEADER_NAME_XSRF,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
    SESSION_REFRESH_TOKEN_KEY,
)
from ctao_shared.db import decrypt_token, encrypt_token

from auth_service.oauth_client import oauth

settings = get_settings()
REFRESH_BUFFER_SECONDS = settings.REFRESH_BUFFER_SECONDS


@pytest.mark.anyio
async def test_login_stores_encrypted_refresh_token_in_redis(
    auth_client,
    fake_redis,
):
    """After OAuth callback, Redis session must contain an encrypted RT."""
    with patch(
        "auth_service.routers.oidc.oauth.ctao.authorize_access_token",
        return_value={
            "access_token": "real-access-token",
            "expires_in": 3600,
            "refresh_token": "real-refresh-token",
            "userinfo": {
                "sub": "some-iam-sub",
                "email": "user@example.com",
                "given_name": "Test",
                "family_name": "User",
            },
        },
    ):
        r = await auth_client.get(
            "/auth/oidc/callback",
            params={"code": "fake-code", "state": "fake-state"},
        )

    assert r.status_code in (200, 302, 307), f"Unexpected status: {r.status_code}"

    # Session cookie must be set
    session_id = r.cookies.get(COOKIE_NAME_MAIN_SESSION)
    assert session_id is not None, "No session cookie set after login"

    # Redis key must exist
    raw = await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    assert raw is not None, "No session found in Redis after login"

    session = json.loads(raw)

    # Core identity fields
    assert session.get("app_user_id") is not None
    assert session.get(SESSION_ACCESS_TOKEN_KEY) is not None
    assert session.get(SESSION_ACCESS_TOKEN_EXPIRY_KEY) is not None

    # Refresh token must be present and encrypted
    enc_rt = session.get(SESSION_REFRESH_TOKEN_KEY)
    assert enc_rt is not None, "Refresh token missing from Redis session"
    assert (
        enc_rt != "real-refresh-token"
    ), "Refresh token must be stored encrypted, not as plaintext"
    # Fernet-encrypted tokens always start with "gAAAAA"
    assert enc_rt.startswith("gAAAAA"), f"Unexpected encrypted RT format: {enc_rt[:10]}"


@pytest.mark.anyio
async def test_access_token_refresh_updates_session_in_redis(
    auth_client,
    as_user,
    fake_redis,
):
    """
    When iam_at_exp is within REFRESH_BUFFER_SECONDS, any authenticated
    request should trigger a token refresh and update iam_at, iam_at_exp,
    and iam_rt in Redis.
    """
    user, session_id = await as_user()
    assert session_id is not None

    # Overwrite the session with an AT that's about to expire
    old_enc_rt = encrypt_token("old-refresh-token")
    session_data = {
        "app_user_id": user.id,
        "iam_sub": "test-sub-123",
        "iam_email": "u@example.org",
        "first_name": "Ada",
        "last_name": "Lovelace",
        SESSION_ACCESS_TOKEN_KEY: "old-access-token",
        SESSION_ACCESS_TOKEN_EXPIRY_KEY: time.time() + (REFRESH_BUFFER_SECONDS - 100),
        SESSION_REFRESH_TOKEN_KEY: old_enc_rt,
    }
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(session_data),
    )
    with patch.object(
        oauth.ctao,
        "fetch_access_token",
        return_value={
            "access_token": "new-access-token",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token",
        },
    ):
        r = await auth_client.get(
            "/auth/me",
            cookies={COOKIE_NAME_MAIN_SESSION: session_id},
        )

    assert r.status_code == 200, f"Unexpected status: {r.status_code}"

    # Re-read session from Redis
    raw = await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    assert raw is not None, "Session disappeared from Redis after refresh"
    updated = json.loads(raw)

    # Access token must be updated
    assert (
        updated[SESSION_ACCESS_TOKEN_KEY] == "new-access-token"
    ), "Access token was not updated in Redis"

    # Expiry must be pushed well into the future
    assert (
        updated[SESSION_ACCESS_TOKEN_EXPIRY_KEY] > time.time() + 60
    ), "New expiry is not far enough in the future"

    # Refresh token must be rotated and still encrypted
    new_enc_rt = updated.get(SESSION_REFRESH_TOKEN_KEY)
    assert new_enc_rt is not None, "Refresh token missing after rotation"
    assert new_enc_rt != old_enc_rt, "Refresh token was not rotated"
    assert (
        new_enc_rt != "new-refresh-token"
    ), "Rotated refresh token must be stored encrypted, not plaintext"
    assert (
        decrypt_token(new_enc_rt) == "new-refresh-token"
    ), "Decrypted rotated RT does not match expected value"


@pytest.mark.anyio
async def test_logout_clears_redis_session_and_cookie(
    auth_client,
    as_user,
    fake_redis,
):
    """Logout must delete the Redis session key and clear the session cookie."""
    await as_user()
    session_id = auth_client.cookies.get(COOKIE_NAME_MAIN_SESSION)
    assert session_id is not None, "as_user did not set session cookie on client"

    # Confirm key exists before logout
    assert (
        await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is not None
    ), "Session should exist in Redis before logout"

    csrf_token = "test-csrf-token"

    r = await auth_client.post(
        "/auth/logout_session",
        cookies={
            COOKIE_NAME_MAIN_SESSION: session_id,
            COOKIE_NAME_XSRF: csrf_token,
        },
        headers={HEADER_NAME_XSRF: csrf_token},
    )
    assert r.status_code == 200, f"Unexpected status: {r.status_code}"

    # Redis key must be gone
    remaining = await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    assert remaining is None, "Session key still exists in Redis after logout"

    # Cookie must be cleared via Set-Cookie header
    set_cookie = r.headers.get("set-cookie", "")
    assert (
        COOKIE_NAME_MAIN_SESSION in set_cookie
    ), "Session cookie name not found in Set-Cookie header"
    assert (
        "max-age=0" in set_cookie.lower() or "max_age=0" in set_cookie.lower()
    ), "Cookie was not expired (max-age=0 not found in Set-Cookie)"
