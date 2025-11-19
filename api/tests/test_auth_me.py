import pytest


@pytest.mark.anyio
async def test_me_from_session_returns_user(client, as_user):
    await as_user(email="u@example.org", first_name="Ada", last_name="Lovelace")
    r = await client.get("/api/users/me_from_session")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "u@example.org"
    assert data["first_name"] == "Ada"
