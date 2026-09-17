from unittest.mock import AsyncMock

import pytest
import requests
from astropy.table import Table

import api.services.object_lookup as object_lookup
from api.services.object_lookup import simbad_suggest


@pytest.mark.anyio
async def test_object_suggest_gates_short_queries(client):
    r = await client.get("/api/object_suggest?q=ab&use_simbad=true&use_ned=true")
    assert r.status_code == 200
    assert r.json() == {"results": []}


@pytest.mark.anyio
async def test_object_suggest_merge_and_cache(
    app,
    client,
    monkeypatch,
):
    calls = {
        "simbad": 0,
        "ned": 0,
    }

    async def fake_simbad(
        q: str,
        limit: int,
    ):
        calls["simbad"] += 1

        return True, [
            {
                "service": "SIMBAD",
                "display_name": "M 31",
                "resolve_name": "M 31",
                "canonical_name": "M 31",
            },
            {
                "service": "SIMBAD",
                "display_name": "M 32",
                "resolve_name": "M 32",
                "canonical_name": "M 32",
            },
        ]

    async def fake_ned(
        q: str,
        limit: int,
    ):
        calls["ned"] += 1

        return True, [
            {
                "service": "NED",
                "display_name": "M31",
                "resolve_name": "M31",
                "canonical_name": "M31",
            },
            {
                "service": "NED",
                "display_name": "M33",
                "resolve_name": "M33",
                "canonical_name": "M33",
            },
        ]

    monkeypatch.setattr(
        "api.services.object_lookup.simbad_suggest",
        fake_simbad,
    )
    monkeypatch.setattr(
        "api.services.object_lookup.ned_suggest",
        fake_ned,
    )

    url = "/api/object_suggest?q=M3&use_simbad=true&use_ned=true&limit=3"

    # First request: cache miss, external suggestors called
    response_1 = await client.get(url)

    assert response_1.status_code == 200
    assert response_1.json() == {
        "results": [
            {
                "service": "SIMBAD",
                "display_name": "M 31",
                "resolve_name": "M 31",
                "canonical_name": "M 31",
            },
            {
                "service": "NED",
                "display_name": "M31",
                "resolve_name": "M31",
                "canonical_name": "M31",
            },
            {
                "service": "SIMBAD",
                "display_name": "M 32",
                "resolve_name": "M 32",
                "canonical_name": "M 32",
            },
        ]
    }

    assert calls == {
        "simbad": 1,
        "ned": 1,
    }

    # the internal cache-control field must not be exposed publicly
    assert "complete" not in response_1.json()

    # Second identical request should be served from Redis
    response_2 = await client.get(url)

    assert response_2.status_code == 200
    assert response_2.json() == response_1.json()

    # Suggestors were not called again
    assert calls == {
        "simbad": 1,
        "ned": 1,
    }


@pytest.mark.anyio
async def test_object_suggest_does_not_cache_partial_results(
    app,
    client,
    monkeypatch,
):
    calls = {
        "simbad": 0,
        "ned": 0,
    }

    async def fake_simbad(
        q: str,
        limit: int,
    ):
        calls["simbad"] += 1

        # SIMBAD timed out or otherwise returned an incomplete response
        return False, []

    async def fake_ned(
        q: str,
        limit: int,
    ):
        calls["ned"] += 1

        return True, [
            {
                "service": "NED",
                "display_name": "Cigar Galaxy",
                "resolve_name": "M82",
                "canonical_name": "M82",
            }
        ]

    monkeypatch.setattr(
        "api.services.object_lookup.simbad_suggest",
        fake_simbad,
    )
    monkeypatch.setattr(
        "api.services.object_lookup.ned_suggest",
        fake_ned,
    )

    url = "/api/object_suggest?q=cigar&use_simbad=true&use_ned=true&limit=15"

    response_1 = await client.get(url)

    assert response_1.status_code == 200
    assert response_1.json() == {
        "results": [
            {
                "service": "NED",
                "display_name": "Cigar Galaxy",
                "resolve_name": "M82",
                "canonical_name": "M82",
            }
        ]
    }

    assert "complete" not in response_1.json()
    assert calls == {
        "simbad": 1,
        "ned": 1,
    }

    # because the first result was incomplete it must not have been cached
    response_2 = await client.get(url)

    assert response_2.status_code == 200
    assert response_2.json() == response_1.json()

    # both services are called again, proving there was no cache hit
    assert calls == {
        "simbad": 2,
        "ned": 2,
    }


@pytest.mark.anyio
async def test_simbad_suggest_uses_common_name_query(
    monkeypatch,
):
    executed_queries: list[str] = []

    def fake_run_tap_sync(
        url: str,
        adql: str,
        maxrec: int = 50,
        timeout: float = 5.0,
    ):
        executed_queries.append(adql)

        # First call: exact query returns no rows
        if "i.id =" in adql:
            return Table(
                names=("matched_id", "main_id"),
                dtype=("U100", "U100"),
            )

        # Second call: targeted common-name query succeeds
        if "NAME Cigar%" in adql:
            return Table(
                rows=[
                    (
                        "NAME Cigar Galaxy",
                        "M  82",
                    )
                ],
                names=("matched_id", "main_id"),
            )

        pytest.fail(
            "The broad SIMBAD alias fallback should not run after the common-name query succeeds."
        )

    monkeypatch.setattr(
        "api.services.object_lookup.run_tap_sync",
        fake_run_tap_sync,
    )

    ok, suggestions = await simbad_suggest(
        prefix="cigar",
        limit=15,
    )

    assert ok is True
    assert len(executed_queries) == 2

    assert "i.id =" in executed_queries[0]
    assert "NAME Cigar%" in executed_queries[1]

    assert suggestions
    assert suggestions[0]["service"] == "SIMBAD"
    assert suggestions[0]["resolve_name"] == "NAME Cigar Galaxy"
    assert suggestions[0]["canonical_name"] == "M  82"


@pytest.mark.anyio
async def test_simbad_suggest_exact_catalog_match_returns_early(
    monkeypatch,
):
    executed_queries: list[str] = []

    def fake_run_tap_sync(
        url: str,
        adql: str,
        maxrec: int = 50,
        timeout: float = 5.0,
    ):
        executed_queries.append(adql)

        return Table(
            rows=[
                (
                    "M  82",
                    "M  82",
                )
            ],
            names=("matched_id", "main_id"),
        )

    monkeypatch.setattr(
        "api.services.object_lookup.run_tap_sync",
        fake_run_tap_sync,
    )

    ok, suggestions = await simbad_suggest(
        prefix="m82",
        limit=15,
    )

    assert ok is True
    assert suggestions

    # only the exact lookup should run
    assert len(executed_queries) == 1
    assert "i.id =" in executed_queries[0]


@pytest.mark.anyio
async def test_simbad_suggest_timeout_returns_incomplete(
    monkeypatch,
):
    def fake_run_tap_sync(
        url: str,
        adql: str,
        maxrec: int = 50,
        timeout: float = 5.0,
    ):
        raise requests.Timeout("SIMBAD timed out")

    monkeypatch.setattr(
        "api.services.object_lookup.run_tap_sync",
        fake_run_tap_sync,
    )

    ok, suggestions = await simbad_suggest(
        prefix="cigar",
        limit=15,
    )

    assert ok is False
    assert suggestions == []


@pytest.mark.asyncio
async def test_object_resolve_skips_ned_for_short_non_catalog_name(
    monkeypatch,
):
    ned_mock = AsyncMock()

    monkeypatch.setattr(
        object_lookup,
        "ned_resolve_via_objectlookup",
        ned_mock,
    )

    result = await object_lookup.object_resolve_impl(
        resolve_name="cra",
        use_simbad=False,
        use_ned=True,
    )

    assert result == {"results": []}
    ned_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_object_resolve_allows_short_catalog_name_for_ned(
    monkeypatch,
):
    ned_result = {
        "service": "NED",
        "name": "MESSIER 001",
        "canonical_name": "MESSIER 001",
        "ra": 83.6331,
        "dec": 22.0145,
    }

    ned_mock = AsyncMock(return_value=ned_result)

    monkeypatch.setattr(
        object_lookup,
        "ned_resolve_via_objectlookup",
        ned_mock,
    )

    result = await object_lookup.object_resolve_impl(
        resolve_name="M1",
        use_simbad=False,
        use_ned=True,
    )

    assert result["results"] == [ned_result]
    ned_mock.assert_awaited_once_with("M1")
