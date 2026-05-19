from urllib.parse import urlparse

import pytest
from fastapi import HTTPException

from api.opus import (
    _guess_preview_mime,
    _opus_cfg,
    _validate_opus_href,
    _validate_opus_path_segment,
    _xml_to_json,
)


def test_guess_preview_mime_by_rid_and_extension():
    assert _guess_preview_mime("log.txt", "stdout").startswith("text/plain")
    assert _guess_preview_mime("plot.png", "excess_map").startswith("image/")
    assert _guess_preview_mime("prov.json", "provjson").startswith("application/json")
    assert _guess_preview_mime("file.nobodyknows", None) == "application/octet-stream"


def test_xml_to_json_basic():
    xml = "<root><a>1</a></root>"
    d = _xml_to_json(xml)
    assert isinstance(d, dict)
    assert "root" in d


def test_guess_preview_mime_case_and_weird_ext():
    # case-insensitive extension
    assert _guess_preview_mime("PLOT.PNG", "whatever").startswith("image/")

    # role-only override
    assert _guess_preview_mime("noext", "provjson").startswith("application/json")

    # ambiguous extension -> still safe default
    assert _guess_preview_mime("data.bin", "unknown") == "application/octet-stream"


def test_xml_to_json_bad_xml_returns_raw_fallback():
    bad_xml = "<root><unclosed>"
    d = _xml_to_json(bad_xml)
    assert isinstance(d, dict)
    assert d == {"raw": bad_xml}


def test_xml_to_json_attributes_and_lists():
    xml = """
    <root>
      <item id="1">A</item>
      <item id="2">B</item>
    </root>
    """
    d = _xml_to_json(xml)
    items = d["root"]["item"]
    if isinstance(items, dict):  # single-item edge
        items = [items]
    assert len(items) == 2


@pytest.mark.anyio
async def test_get_job_rejects_invalid_job_id(client, force_api_identity):
    r = await client.get("/api/opus/jobs/../secret")
    assert r.status_code in (400, 404)


def test_validate_opus_path_segment_rejects_path_traversal():
    with pytest.raises(HTTPException):
        _validate_opus_path_segment("../secret", field_name="job_id")


def test_validate_opus_path_segment_accepts_common_job_id():
    assert _validate_opus_path_segment("abc-123_DEF.456", field_name="job_id") == "abc-123_DEF.456"


def test_validate_opus_href_rejects_disallowed_host():
    with pytest.raises(HTTPException):
        _validate_opus_href("https://evil.example/result.fits")


def test_validate_opus_path_segment_accepts_underscore_rid():
    assert _validate_opus_path_segment("excess_map_fits", field_name="rid") == "excess_map_fits"


def test_validate_opus_href_accepts_opus_store_url():
    host = urlparse(_opus_cfg()["OPUS_BASE"]).netloc
    href = f"https://{host}/store?ID=dbb866"
    assert str(_validate_opus_href(href)) == href
