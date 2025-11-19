import json
import pytest
from sqlalchemy import select
from api.constants import SESSION_KEY_PREFIX, CTAO_PROVIDER_NAME
from api.models import UserRefreshToken


@pytest.mark.anyio
async def test_logout_deletes_session_and_refresh_tokens(
    client, as_user, db_session, fake_redis
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
    r = await client.post("/api/auth/logout_session", cookies=cookies)
    assert r.status_code == 200

    # Session key gone
    assert await fake_redis.get(f"{SESSION_KEY_PREFIX}{session_id}") is None

    # Refresh token deleted
    res = await db_session.execute(
        select(UserRefreshToken).where(UserRefreshToken.user_id == user.id)
    )
    assert res.scalars().first() is None
