import json

import pytest
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    COOKIE_NAME_XSRF,
    HEADER_NAME_XSRF,
    SESSION_KEY_PREFIX,
)


@pytest.mark.anyio
async def test_logout_deletes_session_and_refresh_tokens(auth_client, as_user, fake_redis):
    await as_user()

    # Create a server-side session in Redis
    session_id = "session-123"
    session_data = {
        "app_user_id": 1,
        "access_token": "x",
        "refresh_token": "enc-refresh-token",
    }
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(session_data),
    )

    csrf_token = "test-csrf-token"
    r = await auth_client.post(
        "/auth/logout_session",
        cookies={
            COOKIE_NAME_MAIN_SESSION: session_id,
            COOKIE_NAME_XSRF: csrf_token,
        },
        headers={HEADER_NAME_XSRF: csrf_token},
    )
    assert r.status_code == 200

    # Session key (and embedded refresh token) gone from Redis
    assert await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is None
