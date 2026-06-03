import pytest

from api.config import get_api_settings


@pytest.mark.anyio
async def test_datalink_valid_hess_id(client, monkeypatch):
    monkeypatch.setenv("DATALINK_TEST_DOWNLOAD_URL", "")
    get_api_settings.cache_clear()

    r = await client.get("/api/datalink", params=[("ID", "ivo://padc.obspm/hess#123")])

    assert r.status_code == 200
    xml = r.text

    # Zero-padded obs_id_000123 in the synthesized URL
    assert "hess_dl3_dr1_obs_id_000123.fits.gz" in xml


@pytest.mark.anyio
async def test_datalink_uses_configured_test_download_url(client, monkeypatch):
    test_url = (
        "https://globe-door.ifh.de:2880/"
        "pnfs/ifh.de/acs/cta/diskonly/oidc-test-bas/public/test-file.txt"
    )

    monkeypatch.setenv("DATALINK_TEST_DOWNLOAD_URL", test_url)
    get_api_settings.cache_clear()

    r = await client.get("/api/datalink", params=[("ID", "ivo://padc.obspm/hess#123")])

    assert r.status_code == 200
    xml = r.text
    assert test_url in xml
    assert "hess_dl3_dr1_obs_id_000123.fits.gz" not in xml
