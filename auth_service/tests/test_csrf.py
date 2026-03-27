import pytest
from ctao_shared.constants import COOKIE_NAME_MAIN_SESSION


@pytest.mark.anyio
async def test_logout_requires_xsrf(auth_client, as_user):
    _, session_id = await as_user()
    r = await auth_client.post(
        "/auth/logout_session",
        cookies={COOKIE_NAME_MAIN_SESSION: session_id},
    )
    assert r.status_code in (401, 403)
