from __future__ import annotations

import secrets
from functools import lru_cache

from auth_service.config import AuthSettings, get_auth_settings
from ctao_shared.constants import COOKIE_NAME_XSRF
from ctao_shared.security import require_xsrf
from fastapi import Request, Response


@lru_cache
def _settings() -> AuthSettings:
    return get_auth_settings()


def _new_token() -> str:
    # 32 bytes -> URL-safe token (~43 chars)
    return secrets.token_urlsafe(32)


def ensure_xsrf_cookie(request: Request, response: Response) -> str:
    """
    Ensure XSRF-TOKEN cookie exists; if missing, create it.
    Cookie must be readable by JS (httponly=False) so SPA can send it in a header.
    """
    token = request.cookies.get(COOKIE_NAME_XSRF)
    if token:
        return token

    token = _new_token()

    base = dict(_settings().cookie_params)

    # XSRF must be readable by JS:
    base["httponly"] = False

    # keep path="/" so it works for /api/* and /auth/* routes
    base["path"] = "/"

    response.set_cookie(
        key=COOKIE_NAME_XSRF,
        value=token,
        max_age=_settings().SESSION_DURATION_SECONDS,
        **base,
    )
    return token


__all__ = ["ensure_xsrf_cookie", "require_xsrf"]
