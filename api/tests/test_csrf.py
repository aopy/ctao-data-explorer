from __future__ import annotations

import pytest
from ctao_shared.constants import COOKIE_NAME_XSRF, HEADER_NAME_XSRF


@pytest.mark.anyio
async def test_query_history_post_requires_xsrf(client, force_api_identity):
    r = await client.post(
        "/api/query-history",
        json={"query_params": {"q": "test"}, "results": {"rows": []}},
        cookies={COOKIE_NAME_XSRF: "csrf-token"},
    )

    assert r.status_code == 403
    assert r.json()["detail"] == "CSRF token missing or invalid"


@pytest.mark.anyio
async def test_query_history_post_accepts_matching_xsrf(client, force_api_identity):
    token = "csrf-token"

    r = await client.post(
        "/api/query-history",
        json={"query_params": {"q": "test"}, "results": {"rows": []}},
        cookies={COOKIE_NAME_XSRF: token},
        headers={HEADER_NAME_XSRF: token},
    )

    assert r.status_code == 200


@pytest.mark.anyio
async def test_opus_create_job_requires_xsrf(client, force_api_identity):
    r = await client.post(
        "/api/opus/jobs",
        json={
            "obs_ids": ["123"],
            "RA": 83.63,
            "Dec": 22.01,
            "nxpix": 400,
            "nypix": 400,
            "binsz": 0.02,
        },
    )

    assert r.status_code == 403
    assert r.json()["detail"] == "CSRF token missing or invalid"
