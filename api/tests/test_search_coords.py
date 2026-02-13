import urllib.parse

import pytest
from astropy.table import Table


@pytest.mark.anyio
async def test_search_coords_happy_path_adds_datalink(app, client, monkeypatch):
    # Build a small Astropy Table as if returned from TAP
    tab = Table(
        names=("obs_publisher_did", "s_ra"),
        dtype=("U100", float),
        rows=[("ivo://padc.obspm/hess#123", 83.63)],
    )

    # Stub perform_query_with_conditions to return (error=None, table, adql)
    def fake_perform(fields, where_conditions, limit=100, **kwargs):
        assert any("CONTAINS" in w for w in where_conditions)
        return (None, tab, "SELECT ...")

    monkeypatch.setattr("api.main.perform_query_with_conditions", fake_perform)

    # Ensure empty redis store
    app.state.redis.store.clear()

    # Query with equatorial deg coords; no time filter
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
    data = r.json()

    # Columns should include datalink_url appended
    assert "datalink_url" in data["columns"]
    did_idx = data["columns"].index("obs_publisher_did")
    dl_idx = data["columns"].index("datalink_url")
    row = data["data"][0]

    # The datalink URL is our own endpoint with encoded DID
    encoded = urllib.parse.quote(row[did_idx], safe="")
    assert row[dl_idx].endswith(f"/api/datalink?ID={encoded}")

    # Response should be cached
    assert any(k.startswith("search:") for k in app.state.redis.store.keys())


@pytest.mark.anyio
async def test_search_coords_requires_coords_or_time(client):
    r = await client.get("/api/search_coords")
    assert r.status_code == 400
    assert "Provide Coordinates or Time Interval" in r.json()["detail"]
