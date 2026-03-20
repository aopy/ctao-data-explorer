import pytest


@pytest.mark.anyio
async def test_health_live(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_ready(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_convert_time_isot_roundtrip(client):
    payload = {
        "value": "2024-01-01T00:00:00",
        "input_format": "isot",
        "input_scale": "utc",
    }
    r = await client.post("/api/convert_time", json=payload)
    assert r.status_code == 200
    data = r.json()
    # Basic shape + types
    for k in ("utc_isot", "tt_isot"):
        assert isinstance(data[k], str)
    for k in ("utc_mjd", "tt_mjd"):
        assert isinstance(data[k], (float, int))


@pytest.mark.anyio
async def test_convert_time_mjd(client):
    payload = {"value": "60000.0", "input_format": "mjd", "input_scale": "utc"}
    r = await client.post("/api/convert_time", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["utc_mjd"], (float, int))


@pytest.mark.anyio
async def test_convert_time_met_requires_epoch(client):
    payload = {"value": "10", "input_format": "met"}
    r = await client.post("/api/convert_time", json=payload)
    assert r.status_code == 400
    assert "met_epoch_isot required" in r.json()["detail"]


@pytest.mark.anyio
async def test_convert_time_met_zero_equals_epoch(client):
    # MET=0 should equal the epoch time
    payload = {
        "value": "0",
        "input_format": "met",
        "met_epoch_isot": "2024-01-01T00:00:00",
        "met_epoch_scale": "utc",
    }
    r = await client.post("/api/convert_time", json=payload)
    assert r.status_code == 200
    data = r.json()
    # Allow fractional seconds in Astropy format, compare prefix
    assert data["utc_isot"].startswith("2024-01-01T00:00:00")
