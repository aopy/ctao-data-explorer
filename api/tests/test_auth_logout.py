import json

import pytest
from auth_service.models import UserRefreshToken
from ctao_shared.constants import CTAO_PROVIDER_NAME, SESSION_KEY_PREFIX
from sqlalchemy import select


@pytest.mark.anyio
async def test_logout_deletes_session_and_refresh_tokens(
    auth_client, as_user, db_session, fake_redis
):
    user = await as_user()
    # Create a refresh token row
    rt = UserRefreshToken(
        user_id=user.id,
        iam_provider_name=CTAO_PROVIDER_NAME,
        encrypted_refresh_token="enc",
    )
    db_session.add(rt)
    await db_session.commit()

    # Create a server-side session in redis
    session_id = "session-123"
    await fake_redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        3600,
        json.dumps({"app_user_id": user.id, "access_token": "x"}),
    )

    # Send cookie to endpoint
    cookies = {"ctao_session_main": session_id}
    r = await auth_client.post("/api/auth/logout_session", cookies=cookies)
    assert r.status_code == 200

    # Session key gone
    assert await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is None

    # Refresh token deleted
    res = await db_session.execute(
        select(UserRefreshToken).where(UserRefreshToken.user_id == user.id)
    )
    assert res.scalars().first() is None
