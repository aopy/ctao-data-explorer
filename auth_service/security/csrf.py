import secrets

from ctao_shared.config import get_settings
from ctao_shared.constants import COOKIE_NAME_XSRF, HEADER_NAME_XSRF
from fastapi import HTTPException, Request, Response, status

# COOKIE_NAME_XSRF = "XSRF-TOKEN"
# HEADER_NAME_XSRF = "X-XSRF-TOKEN"

settings = get_settings()


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

    base = dict(settings.cookie_params)

    # XSRF must be readable by JS:
    base["httponly"] = False

    # keep path="/" so it works for /api/* and /auth/* routes
    base["path"] = "/"

    response.set_cookie(
        key=COOKIE_NAME_XSRF,
        value=token,
        max_age=settings.SESSION_DURATION_SECONDS,
        **base,
    )
    return token


def require_xsrf(request: Request) -> None:
    """
    Double-submit cookie CSRF check:
    - XSRF-TOKEN cookie must exist
    - X-XSRF-TOKEN header must match cookie
    """
    cookie_val = request.cookies.get(COOKIE_NAME_XSRF)
    header_val = request.headers.get(HEADER_NAME_XSRF)

    if not cookie_val or not header_val or header_val != cookie_val:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
