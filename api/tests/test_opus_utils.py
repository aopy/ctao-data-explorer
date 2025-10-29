from api.opus import _guess_preview_mime, _xml_to_json

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
