from __future__ import annotations

from fastapi import HTTPException, Request, status

from ctao_shared.constants import COOKIE_NAME_XSRF, HEADER_NAME_XSRF


def require_xsrf(request: Request) -> None:
    """
    Double-submit cookie CSRF check.

    The readable XSRF cookie must be present and match the X-XSRF-TOKEN header.
    """
    cookie_val = request.cookies.get(COOKIE_NAME_XSRF)
    header_val = request.headers.get(HEADER_NAME_XSRF)

    if not cookie_val or not header_val or header_val != cookie_val:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )


def require_xsrf_dependency(request: Request) -> None:
    """FastAPI dependency wrapper for state-mutating endpoints."""
    require_xsrf(request)
