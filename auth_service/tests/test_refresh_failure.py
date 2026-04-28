import json
import time
from unittest.mock import patch

import pytest
from authlib.integrations.base_client.errors import OAuthError
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
    SESSION_REFRESH_TOKEN_KEY,
)

from auth_service.config import get_auth_settings
from auth_service.crypto import encrypt_token

settings = get_auth_settings()


@pytest.mark.anyio
async def test_refresh_failure_forces_401_and_deletes_session(auth_client, as_user, fake_redis):
    user, session_id = await as_user(access_token="old-at", refresh_token_plain="old-rt")
    assert session_id

    session_data = {
        "app_user_id": user.id,
        "iam_sub": "sub-123",
        "iam_email": "u@example.org",
        "first_name": "Ada",
        "last_name": "Lovelace",
        SESSION_ACCESS_TOKEN_KEY: "old-at",
        SESSION_ACCESS_TOKEN_EXPIRY_KEY: time.time() + (settings.REFRESH_BUFFER_SECONDS - 5),
        SESSION_REFRESH_TOKEN_KEY: encrypt_token("old-rt"),
    }
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps(session_data),
    )

    with patch(
        "auth_service.routers.auth.oauth.ctao.fetch_access_token",
        side_effect=OAuthError(error="invalid_grant", description="revoked"),
    ):
        r = await auth_client.get("/auth/me", cookies={COOKIE_NAME_MAIN_SESSION: session_id})

    assert r.status_code == 401, r.text
    assert await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is None
