from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from download_service.config import get_download_settings
from download_service.main import create_app
from download_service.token_exchange import TokenExchangeDenied


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app(monkeypatch) -> FastAPI:
    monkeypatch.setenv("IAM_TOKEN_ENDPOINT", "https://iam.example/token")
    monkeypatch.setenv("DOWNLOAD_SERVICE_CLIENT_ID", "client-id")
    monkeypatch.setenv("DOWNLOAD_SERVICE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON", '["globe-door.ifh.de:2880"]')
    monkeypatch.setenv("DOWNLOAD_TOKEN_EXCHANGE_AUDIENCE", "https://wlcg.cern.ch/jwt/v1/any")
    monkeypatch.setenv("DOWNLOAD_TOKEN_EXCHANGE_SCOPE", "storage.read:/public/")
    get_download_settings.cache_clear()
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_signed_urls_requires_bearer(client: AsyncClient):
    r = await client.post(
        "/api/v1/signed-urls",
        json={"files": ["https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/sdc/data/file1.dat"]},
    )

    assert r.status_code == 401


@pytest.mark.anyio
async def test_signed_urls_rejects_disallowed_host(client: AsyncClient):
    r = await client.post(
        "/api/v1/signed-urls",
        headers={"Authorization": "Bearer USER-TOKEN"},
        json={"files": ["https://evil.example/pnfs/ifh.de/acs/sdc/data/file1.dat"]},
    )

    assert r.status_code == 400
    data = r.json()
    assert data["detail"]["error"] == "HOST_NOT_ALLOWED"
    assert data["detail"]["message"] == "Storage host is not allowed"


@pytest.mark.anyio
async def test_signed_urls_success(client: AsyncClient, monkeypatch):
    async def fake_exchange_file_token(
        *,
        subject_token,
        scope,
        audience,
        validity_seconds,
        settings,
    ):
        assert subject_token == "USER-TOKEN"
        assert scope == "storage.read:/pnfs/ifh.de/acs/sdc/data/file1.dat"
        assert audience == "https://globe-door.ifh.de:2880/"
        assert validity_seconds == 3600
        assert settings.DOWNLOAD_SERVICE_CLIENT_ID == "client-id"
        return "FILE-TOKEN", datetime.now(UTC) + timedelta(seconds=3600)

    monkeypatch.setattr(
        "download_service.service.exchange_file_token",
        fake_exchange_file_token,
    )

    r = await client.post(
        "/api/v1/signed-urls",
        headers={"Authorization": "Bearer USER-TOKEN"},
        json={
            "files": ["https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/sdc/data/file1.dat"],
            "validity": "PT1H",
        },
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["token_exchange_count"] == 1
    assert data["signed_urls"][0]["access_token"] == "FILE-TOKEN"
    assert data["signed_urls"][0]["credential_type"] == "bearer_token"
    assert data["signed_urls"][0]["storage_url"].endswith("/file1.dat")


@pytest.mark.anyio
async def test_signed_urls_partial_success(client: AsyncClient, monkeypatch):
    async def fake_exchange_file_token(
        *,
        subject_token,
        scope,
        audience,
        validity_seconds,
        settings,
    ):
        _ = subject_token, audience, validity_seconds, settings

        if scope.endswith("file2.dat"):
            raise TokenExchangeDenied()

        return "FILE-TOKEN-1", datetime.now(UTC) + timedelta(seconds=3600)

    monkeypatch.setattr(
        "download_service.service.exchange_file_token",
        fake_exchange_file_token,
    )

    r = await client.post(
        "/api/v1/signed-urls",
        headers={"Authorization": "Bearer USER-TOKEN"},
        json={
            "files": [
                "https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/sdc/data/file1.dat",
                "https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/sdc/data/file2.dat",
            ],
            "validity": "PT1H",
        },
    )

    assert r.status_code == 206, r.text
    data = r.json()
    assert len(data["signed_urls"]) == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["code"] == "AUTHORIZATION_DENIED"


@pytest.mark.anyio
async def test_signed_url_status_does_not_return_tokens(client: AsyncClient, monkeypatch):
    async def fake_exchange_file_token(
        *,
        subject_token,
        scope,
        audience,
        validity_seconds,
        settings,
    ):
        _ = subject_token, scope, audience, validity_seconds, settings
        return "FILE-TOKEN", datetime.now(UTC) + timedelta(seconds=3600)

    monkeypatch.setattr(
        "download_service.service.exchange_file_token",
        fake_exchange_file_token,
    )

    r = await client.post(
        "/api/v1/signed-urls",
        headers={"Authorization": "Bearer USER-TOKEN"},
        json={"files": ["https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/sdc/data/file1.dat"]},
    )

    assert r.status_code == 200
    request_id = r.json()["request_id"]

    r2 = await client.get(
        f"/api/v1/signed-urls/{request_id}",
        headers={"Authorization": "Bearer USER-TOKEN"},
    )

    assert r2.status_code == 200
    status_data = r2.json()
    assert "access_token" not in status_data
    assert status_data["file_count"] == 1
    assert status_data["status"] == "completed"


@pytest.mark.anyio
async def test_signed_urls_uses_configured_token_exchange_scope_and_audience(
    client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setenv("DOWNLOAD_TOKEN_EXCHANGE_AUDIENCE", "https://wlcg.cern.ch/jwt/v1/any")
    monkeypatch.setenv("DOWNLOAD_TOKEN_EXCHANGE_SCOPE", "storage.read:/public/")
    get_download_settings.cache_clear()

    real_post = AsyncClient.post

    async def fake_post(self, url, *args, data=None, auth=None, **kwargs):
        if str(url).startswith("/api/"):
            return await real_post(self, url, *args, data=data, auth=auth, **kwargs)

        assert url == "https://iam.example/token"
        assert data is not None

        assert data["scope"] == "storage.read:/public/"
        assert data["audience"] == "https://wlcg.cern.ch/jwt/v1/any"

        assert data["grant_type"] == "urn:ietf:params:oauth:grant-type:token-exchange"
        assert data["subject_token"] == "USER-TOKEN"
        assert data["subject_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
        assert data["requested_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
        assert auth == ("client-id", "client-secret")

        return Response(
            200,
            json={
                "access_token": "FILE-TOKEN",
                "expires_in": 3600,
                "scope": "storage.read:/public/",
                "token_type": "Bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
            },
        )

    monkeypatch.setattr(AsyncClient, "post", fake_post)

    r = await client.post(
        "/api/v1/signed-urls",
        headers={"Authorization": "Bearer USER-TOKEN"},
        json={
            "files": [
                "https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/cta/diskonly/oidc-test-bas/public/test-file.txt"
            ],
            "validity": "PT1H",
        },
    )

    assert r.status_code == 200, r.text
    data = r.json()

    assert data["token_exchange_count"] == 1
    assert data["signed_urls"][0]["access_token"] == "FILE-TOKEN"
    assert data["signed_urls"][0]["storage_url"] == (
        "https://globe-door.ifh.de:2880/pnfs/ifh.de/acs/cta/diskonly/oidc-test-bas/public/test-file.txt"
    )
