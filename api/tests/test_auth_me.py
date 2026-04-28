import json

import pytest
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_KEY_PREFIX,
    SESSION_USER_ID_KEY,
)


@pytest.mark.anyio
async def test_me_returns_user(auth_client, as_user, fake_redis):
    user, _ = await as_user(email="u@example.org", first_name="Ada", last_name="Lovelace")

    session_id = "session-me-1"
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(
            {
                SESSION_USER_ID_KEY: user.id,
                SESSION_IAM_EMAIL_KEY: "u@example.org",
                SESSION_IAM_GIVEN_NAME_KEY: "Ada",
                SESSION_IAM_FAMILY_NAME_KEY: "Lovelace",
                SESSION_IAM_SUB_KEY: "sub-123",
            }
        ),
    )

    r = await auth_client.get(
        "/auth/me",
        cookies={COOKIE_NAME_MAIN_SESSION: session_id},
    )
    assert r.status_code == 200
    data = r.json()

    assert data["app_user_id"] == user.id
    assert data["email"] == "u@example.org"
    assert data["first_name"] == "Ada"
    assert data["last_name"] == "Lovelace"
    assert data["sub"] == "sub-123"
