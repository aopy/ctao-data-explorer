import pytest
from astropy.table import Table


@pytest.mark.anyio
async def test_energy_only_search_uses_overlap_conditions(client, app, monkeypatch):
    """
    Energy-only search should be accepted, and it should add the overlap constraints:
      energy_max >= user_min
      energy_min <= user_max
    """

    # Stub TAP_SCHEMA to "know" energy columns exist
    async def fake_get_cols(tap_url: str, table: str) -> set[str]:
        return {"energy_min", "energy_max"}

    monkeypatch.setattr("api.main.get_tap_table_columns", fake_get_cols)

    # Stub TAP execution and assert filters are present in where_conditions
    tab = Table(
        names=("obs_publisher_did", "energy_min", "energy_max"),
        dtype=("U100", float, float),
        rows=[("ivo://padc.obspm/hess#123", 0.25, 120.0)],
    )

    def fake_perform(fields, where_conditions, limit=100):
        assert any("energy_max >=" in w for w in where_conditions)
        assert any("energy_min <=" in w for w in where_conditions)
        return (None, tab, "SELECT ...")

    monkeypatch.setattr("api.main.perform_query_with_conditions", fake_perform)

    # Ensure redis is empty for deterministic behavior
    app.state.redis.store.clear()

    r = await client.get(
        "/api/search_coords",
        params={
            "tap_url": "https://example.invalid/tap",
            "obscore_table": "hess_dr.obscore",
            "energy_min": 0.24408458,
            "energy_max": 100.978134,
        },
    )
    assert r.status_code == 200
    payload = r.json()
    assert "columns" in payload
    assert "data" in payload


@pytest.mark.anyio
async def test_energy_only_search_rejects_if_energy_columns_missing(client, monkeypatch):
    """
    If energy filters are requested but the table doesn't provide energy_min/energy_max,
    endpoint should return 400 with a clear message.
    """

    async def fake_get_cols(tap_url: str, table: str) -> set[str]:
        return {"s_ra", "s_dec"}  # no energy columns

    monkeypatch.setattr("api.main.get_tap_table_columns", fake_get_cols)

    r = await client.get(
        "/api/search_coords",
        params={
            "tap_url": "https://example.invalid/tap",
            "obscore_table": "hess_dr.obscore_sdc",
            "energy_min": 1.0,
        },
    )
    assert r.status_code == 400
    assert "energy_min" in r.json()["detail"].lower()
    assert "energy_max" in r.json()["detail"].lower()


@pytest.mark.anyio
async def test_optional_only_obs_config_search_applies_filters(client, app, monkeypatch):
    """
    Optional-only search (tracking/pointing/obs_mode) should be accepted.
    Verify where_conditions includes the equality filters.
    """

    async def fake_get_cols(tap_url: str, table: str) -> set[str]:
        return {"tracking_type", "pointing_mode", "obs_mode"}

    monkeypatch.setattr("api.main.get_tap_table_columns", fake_get_cols)

    tab = Table(
        names=("obs_publisher_did", "tracking_type", "pointing_mode", "obs_mode"),
        dtype=("U100", "U20", "U20", "U20"),
        rows=[("ivo://padc.obspm/hess#123", "sidereal", "parallel", "default")],
    )

    def fake_perform(fields, where_conditions, limit=100):
        # Expect exact matches
        assert any("tracking_type = 'sidereal'" in w.lower() for w in where_conditions)
        assert any("pointing_mode = 'parallel'" in w.lower() for w in where_conditions)
        assert any("obs_mode = 'default'" in w.lower() for w in where_conditions)
        return (None, tab, "SELECT ...")

    monkeypatch.setattr("api.main.perform_query_with_conditions", fake_perform)
    app.state.redis.store.clear()

    r = await client.get(
        "/api/search_coords",
        params={
            "tap_url": "https://example.invalid/tap",
            "obscore_table": "hess_dr.obscore",
            "tracking_mode": "sidereal",
            "pointing_mode": "parallel",
            "obs_mode": "default",
        },
    )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_schema_unavailable_energy_probe_true_allows_energy_search(client, app, monkeypatch):
    """
    If TAP_SCHEMA lookup fails (returns empty set), energy search should fall back
    to tap_supports_columns probe. If probe says True, it proceeds.
    """

    async def fake_get_cols(tap_url: str, table: str) -> set[str]:
        return set()  # schema unavailable

    async def fake_probe(tap_url: str, table: str, cols: list[str]) -> bool:
        assert cols == ["energy_min", "energy_max"]
        return True

    monkeypatch.setattr("api.main.get_tap_table_columns", fake_get_cols)
    monkeypatch.setattr("api.main.tap_supports_columns", fake_probe)

    tab = Table(
        names=("obs_publisher_did", "energy_min", "energy_max"),
        dtype=("U100", float, float),
        rows=[("ivo://padc.obspm/hess#123", 0.25, 120.0)],
    )

    def fake_perform(fields, where_conditions, limit=100):
        assert any("energy_max >=" in w for w in where_conditions)
        return (None, tab, "SELECT ...")

    monkeypatch.setattr("api.main.perform_query_with_conditions", fake_perform)
    app.state.redis.store.clear()

    r = await client.get(
        "/api/search_coords",
        params={
            "tap_url": "https://example.invalid/tap",
            "obscore_table": "hess_dr.obscore",
            "energy_min": 10.0,
        },
    )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_schema_unavailable_probe_errors_returns_503(client, monkeypatch):
    """
    If TAP_SCHEMA is unavailable and the fallback probe errors, endpoint should 503.
    """

    async def fake_get_cols(tap_url: str, table: str) -> set[str]:
        return set()  # schema unavailable

    async def fake_probe(tap_url: str, table: str, cols: list[str]) -> bool:
        raise RuntimeError("TAP down")

    monkeypatch.setattr("api.main.get_tap_table_columns", fake_get_cols)
    monkeypatch.setattr("api.main.tap_supports_columns", fake_probe)

    r = await client.get(
        "/api/search_coords",
        params={
            "tap_url": "https://example.invalid/tap",
            "obscore_table": "hess_dr.obscore",
            "energy_min": 10.0,
        },
    )
    assert r.status_code == 503
    assert "tap" in r.json()["detail"].lower()
