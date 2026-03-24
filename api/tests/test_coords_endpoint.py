import pytest


@pytest.mark.anyio
async def test_parse_coords_hmsdms(client):
    payload = {"coord1": "05:34:31.94", "coord2": "+22:00:52.2", "system": "hmsdms"}
    r = await client.post("/api/parse_coords", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["error"] is None
    assert 0 <= data["ra_deg"] <= 360
    assert -90 <= data["dec_deg"] <= 90


@pytest.mark.anyio
async def test_parse_coords_deg_validation(client):
    payload = {"coord1": "400", "coord2": "10", "system": "deg"}
    r = await client.post("/api/parse_coords", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["error"] and "RA must be between 0 and 360" in data["error"]


@pytest.mark.anyio
async def test_parse_coords_gal(client):
    payload = {"coord1": "120.5", "coord2": "-10.0", "system": "gal"}
    r = await client.post("/api/parse_coords", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["error"] is None
    # Should include both RA/Dec (converted) and original l/b
    assert data["l_deg"] == 120.5
    assert data["b_deg"] == -10.0
    assert 0 <= data["ra_deg"] <= 360
