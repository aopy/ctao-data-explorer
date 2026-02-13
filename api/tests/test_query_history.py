import pytest
from astropy.table import Table
from sqlalchemy import select

from api.models import QueryHistory


@pytest.mark.anyio
async def test_search_coords_writes_history(client, as_user, db_session, monkeypatch):
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

    # Ensure dependency thinks we are authenticated
    user = await as_user()

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
    assert rows[0].user_id == user.id
    assert rows[0].results is not None and rows[0].query_params is not None
