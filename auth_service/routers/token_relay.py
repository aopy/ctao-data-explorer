from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from functools import lru_cache
from typing import Any

import httpx
from ctao_shared.constants import COOKIE_NAME_XSRF, HEADER_NAME_XSRF
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from auth_service.config import get_auth_settings
from auth_service.routers.auth import get_required_session_user


@lru_cache
def _settings():
    return get_auth_settings()


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["token-relay"])

# Hop-by-hop headers must not be forwarded (RFC 7230)
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filtered_request_headers(req: Request) -> dict[str, str]:
    """
    Forward most headers, but never forward Cookie/Host/Authorization.
    Authorization will be injected from the session access token.
    """
    out: dict[str, str] = {}
    for k, v in req.headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        if lk in {"host", "cookie", "authorization", "content-length"}:
            continue
        out[k] = v
    return out


def _attach_xsrf_forwarding(req: Request, headers: dict[str, str]) -> None:
    """
    Forward the double-submit CSRF pair to downstream services.

    We intentionally do not forward the main session cookie. The API only needs
    the readable XSRF cookie plus the matching X-XSRF-TOKEN header for CSRF
    validation; authentication is still handled by the injected Bearer token.
    """
    xsrf_cookie = req.cookies.get(COOKIE_NAME_XSRF)
    xsrf_header = req.headers.get(HEADER_NAME_XSRF)

    if xsrf_header:
        headers[HEADER_NAME_XSRF] = xsrf_header

    if xsrf_cookie:
        headers["Cookie"] = f"{COOKIE_NAME_XSRF}={xsrf_cookie}"


def _filtered_response_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers:
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        # let FastAPI set content-length/encoding as needed
        if lk in {"content-length", "transfer-encoding"}:
            continue
        out[k] = v
    return out


def _join_url(base: str, path: str) -> str:
    base = base.rstrip("/")
    path = (path or "").lstrip("/")
    return f"{base}/{path}" if path else base


ASGIApp = Callable[
    [
        MutableMapping[str, Any],
        Callable[[], Awaitable[MutableMapping[str, Any]]],
        Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]

_ASGI_TARGETS: dict[str, ASGIApp] = {}


def register_asgi_target(name: str, app: ASGIApp) -> None:
    _ASGI_TARGETS[name] = app


@router.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def relay(
    service: str,
    path: str,
    request: Request,
    user_session_data: dict = Depends(get_required_session_user),
) -> Response:
    targets = _settings().token_relay_targets
    base = targets.get(service)
    if not base:
        raise HTTPException(status_code=404, detail=f"Unknown relay service '{service}'")

    access_token = user_session_data.get("iam_access_token")
    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"detail": "reauth_required", "reason": "no_access_token"},
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="reauth_required"'
            },
        )

    # Build outgoing request pieces
    headers = _filtered_request_headers(request)
    _attach_xsrf_forwarding(request, headers)
    headers["Authorization"] = f"Bearer {access_token}"

    body = await request.body()

    # ASGI target (tests)
    if base.startswith("asgi://"):
        target_name = base.removeprefix("asgi://").strip("/")
        asgi_app = _ASGI_TARGETS.get(target_name)
        if not asgi_app:
            raise HTTPException(status_code=500, detail="ASGI relay target not registered")

        transport = httpx.ASGITransport(app=asgi_app)
        async with (
            httpx.AsyncClient(transport=transport, base_url="http://asgi") as client
        ):  # NOSONAR(python:S5332) — ASGITransport never opens a socket, the scheme is a placeholder to satisfy httpx's API
            r = await client.request(
                method=request.method,
                url="/" + (path or ""),
                headers=headers,
                params=request.query_params,
                content=body if body else None,
            )

        resp_headers = _filtered_response_headers(r.headers.items())
        return Response(
            content=r.content,
            status_code=r.status_code,
            headers=resp_headers,
            media_type=r.headers.get("content-type"),
        )

    # Normal HTTP target (real deployment)
    downstream_url = _join_url(base, path)

    timeout = httpx.Timeout(_settings().TOKEN_RELAY_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            r = await client.request(
                method=request.method,
                url=downstream_url,
                headers=headers,
                params=request.query_params,
                content=body if body else None,
            )
        except httpx.RequestError as e:
            logger.exception("Token relay error to %s: %s", downstream_url, e)
            raise HTTPException(status_code=502, detail="Downstream service unreachable") from e

    resp_headers = _filtered_response_headers(r.headers.items())
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers=resp_headers,
        media_type=r.headers.get("content-type"),
    )
