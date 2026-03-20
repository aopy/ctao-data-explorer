import pytest


@pytest.mark.anyio
async def test_object_suggest_gates_short_queries(client):
    r = await client.get("/api/object_suggest?q=ab&use_simbad=true&use_ned=true")
    assert r.status_code == 200
    assert r.json() == {"results": []}


@pytest.mark.anyio
async def test_object_suggest_merge_and_cache(app, client, monkeypatch):
    # Fake SIMBAD & NED suggestors
    async def fake_simbad(q, limit):
        return [
            {"service": "SIMBAD", "name": "M 31"},
            {"service": "SIMBAD", "name": "M 32"},
        ]

    async def fake_ned(q, limit):
        return [{"service": "NED", "name": "M31"}, {"service": "NED", "name": "M33"}]

    monkeypatch.setattr("api.main._simbad_suggest", fake_simbad)
    monkeypatch.setattr("api.main._ned_suggest", fake_ned)

    # First call -> cache miss then set
    r1 = await client.get("/api/object_suggest?q=M3&use_simbad=true&use_ned=true&limit=3")
    assert r1.status_code == 200
    data1 = r1.json()["results"]
    # Round-robin: SIMBAD, NED, SIMBAD
    assert [d["service"] for d in data1] == ["SIMBAD", "NED", "SIMBAD"]

    # Verify key exists in fake redis
    cached_keys = list(app.state.redis.store.keys())
    assert any(k.startswith("suggest:") for k in cached_keys)

    # Second call should hit cache and NOT call underlying functions.
    def boom(*args, **kwargs):
        raise AssertionError("Should not be called when cache is present")

    monkeypatch.setattr("api.main._simbad_suggest", boom)
    monkeypatch.setattr("api.main._ned_suggest", boom)

    r2 = await client.get("/api/object_suggest?q=M3&use_simbad=true&use_ned=true&limit=3")
    assert r2.status_code == 200
    assert r2.json()["results"] == data1
