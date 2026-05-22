from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from download_service.config import DownloadSettings

logger = logging.getLogger(__name__)

TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


class TokenExchangeDenied(Exception):
    pass


class TokenExchangeUpstreamError(Exception):
    pass


async def exchange_file_token(
    *,
    subject_token: str,
    scope: str,
    audience: str,
    validity_seconds: int,
    settings: DownloadSettings,
) -> tuple[str, datetime]:
    """
    RFC 8693 token exchange.

    The requested token is scoped to one file/path:
      scope=storage.read:<file_path>

    The audience is normally derived from the storage host, but can be overridden
    with DOWNLOAD_TOKEN_AUDIENCE for storage systems configured with a fixed/default audience.
    """
    data = {
        "grant_type": TOKEN_EXCHANGE_GRANT,
        "subject_token": subject_token,
        "subject_token_type": ACCESS_TOKEN_TYPE,
        "requested_token_type": ACCESS_TOKEN_TYPE,
        "scope": settings.DOWNLOAD_TOKEN_EXCHANGE_SCOPE or scope,
        "audience": settings.DOWNLOAD_TOKEN_EXCHANGE_AUDIENCE or audience,
    }

    data["expires_in"] = str(validity_seconds)

    auth = (settings.DOWNLOAD_SERVICE_CLIENT_ID, settings.DOWNLOAD_SERVICE_CLIENT_SECRET)

    logger.info(
        "Requesting IAM token exchange: scope=%s audience=%s",
        data.get("scope"),
        data.get("audience"),
    )

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(settings.IAM_TOKEN_ENDPOINT, data=data, auth=auth)
        except httpx.RequestError as exc:
            logger.warning("IAM token exchange endpoint unreachable", exc_info=True)
            raise TokenExchangeUpstreamError() from exc

    if response.status_code in {400, 401, 403}:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"raw": response.text[:500]}

        logger.info(
            "IAM denied token exchange: status=%s scope=%s audience=%s error=%s",
            response.status_code,
            scope,
            audience,
            error_payload,
        )
        raise TokenExchangeDenied()

    if response.status_code >= 500:
        logger.warning("IAM token exchange returned upstream error status=%s", response.status_code)
        raise TokenExchangeUpstreamError()

    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"raw": response.text[:500]}

        logger.warning(
            "IAM token exchange returned unexpected error: status=%s error=%s",
            response.status_code,
            error_payload,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "UPSTREAM_ERROR",
                "message": "IAM token exchange endpoint returned an unexpected response",
            },
        )

    try:
        body: dict[str, Any] = response.json()
    except ValueError as exc:
        raise TokenExchangeUpstreamError() from exc

    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise TokenExchangeUpstreamError()

    expires_in = int(body.get("expires_in") or validity_seconds)
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    return token, expires_at
