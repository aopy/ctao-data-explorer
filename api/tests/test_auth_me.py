import json

import pytest
from ctao_shared.constants import SESSION_KEY_PREFIX


@pytest.mark.anyio
async def test_me_from_session_returns_user(auth_client, as_user, fake_redis):
    user = await as_user(email="u@example.org", first_name="Ada", last_name="Lovelace")

    session_id = "session-me-1"
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(
            {
                "app_user_id": user.id,
                "iam_email": "u@example.org",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "iam_sub": "sub-123",
            }
        ),
    )

    r = await auth_client.get(
        "/api/users/me_from_session",
        cookies={"ctao_session_main": session_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == user.id
    assert data["email"] == "u@example.org"
