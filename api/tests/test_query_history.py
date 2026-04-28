import pytest
from astropy.table import Table
from sqlalchemy import select

from api.auth.deps_optional import get_optional_identity
from api.auth.jwt_verifier import VerifiedIdentity
from api.models import QueryHistory


@pytest.mark.anyio
async def test_search_coords_writes_history(client, db_session, monkeypatch):
    # Arrange: stub TAP call to return one row
    tab = Table(
        names=("obs_publisher_did", "s_ra"),
        dtype=("U100", float),
        rows=[("ivo://padc.obspm/hess#123", 83.63)],
    )

    def fake_perform(fields, where_conditions, limit=100, **kwargs):
        assert any("CONTAINS" in w for w in where_conditions)
        return (None, tab, "SELECT ...")

    monkeypatch.setattr("api.main.perform_query_with_conditions", fake_perform)

    # Force optional identity to be present (so history is written)
    fake_ident = VerifiedIdentity(
        sub="sub-test-123",
        email="u@example.org",
        preferred_username=None,
        given_name="Ada",
        family_name="Lovelace",
        name="Ada Lovelace",
        claims={},
    )

    from api.main import app  # local import so app exists

    app.dependency_overrides[get_optional_identity] = lambda: fake_ident
    try:
        # Act
        r = await client.get(
            "/api/search_coords",
            params={
                "coordinate_system": "eq_deg",
                "ra": 83.63,
                "dec": 22.01,
                "search_radius": 5.0,
                "tap_url": "https://example.invalid/tap",
                "obscore_table": "ivoa.obscore",
            },
        )
        assert r.status_code == 200

        # Assert: a QueryHistory row exists
        res = await db_session.execute(select(QueryHistory))
        rows = res.scalars().all()

        assert len(rows) == 1
        assert rows[0].user_sub == fake_ident.sub
        assert rows[0].results is not None
        assert rows[0].query_params is not None
    finally:
        app.dependency_overrides.pop(get_optional_identity, None)
