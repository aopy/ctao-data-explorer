import pytest

@pytest.mark.anyio
async def test_datalink_valid_hess_id(client):
    r = await client.get("/api/datalink", params=[("ID", "ivo://padc.obspm/hess#123")])
    assert r.status_code == 200
    xml = r.text
    # Zero-padded obs_id_000123 in the synthesized URL
    assert "hess_dl3_dr1_obs_id_000123.fits.gz" in xml
    assert "<FIELD name=\"error_message\"" in xml

@pytest.mark.anyio
async def test_datalink_invalid_id(client):
    r = await client.get("/api/datalink", params=[("ID", "notivo://bad")])
    assert r.status_code == 200
    xml = r.text
    assert "NotFoundFault" in xml
    # access_url empty for invalid IDs
    assert "<TD></TD>" in xml  # access_url cell when error
