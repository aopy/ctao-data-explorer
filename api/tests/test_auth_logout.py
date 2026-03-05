import json

import pytest
from ctao_shared.constants import SESSION_KEY_PREFIX


@pytest.mark.anyio
async def test_logout_deletes_session_and_refresh_tokens(auth_client, as_user, fake_redis):
    user = await as_user()

    # Create a server-side session in Redis
    session_id = "session-123"
    session_data = {
        "app_user_id": user.id,
        "access_token": "x",
        "refresh_token": "enc-refresh-token",
    }
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(session_data),
    )

    # Send cookie to endpoint
    cookies = {"ctao_session_main": session_id}
    r = await auth_client.post("/api/auth/logout_session", cookies=cookies)
    assert r.status_code == 200

    # Session key (and embedded refresh token) gone from Redis
    assert await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is None
