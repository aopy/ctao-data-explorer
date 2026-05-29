from __future__ import annotations

import threading

from authlib.integrations.starlette_client import OAuth
from ctao_shared.constants import CTAO_PROVIDER_NAME

from auth_service.config import get_auth_settings

_lock = threading.Lock()

oauth = OAuth()
_registered = False


def _metadata_url_from_settings(s) -> str | None:
    # Preferred explicit metadata URL
    url = (getattr(s, "OIDC_SERVER_METADATA_URL", None) or "").strip()
    if url:
        return url

    # Fallback: build from issuer
    issuer = (getattr(s, "OIDC_ISSUER", None) or "").strip().rstrip("/")
    if issuer:
        return f"{issuer}/.well-known/openid-configuration"

    return None


def get_oauth() -> OAuth:
    """
    Lazy registration:
    - avoids failing at import time during tests
    - avoids requiring env vars unless actually used
    """
    global _registered
    if _registered:
        return oauth
    with _lock:
        if _registered:
            return oauth

        s = get_auth_settings()
        metadata_url = _metadata_url_from_settings(s)
        if not metadata_url:
            raise RuntimeError(
                "Auth service OIDC is not configured: set OIDC_SERVER_METADATA_URL or OIDC_ISSUER"
            )
        oauth.register(
            name=CTAO_PROVIDER_NAME,
            server_metadata_url=metadata_url,
            client_id=s.CTAO_CLIENT_ID,
            client_secret=s.CTAO_CLIENT_SECRET,
            client_kwargs={"scope": "openid profile email offline_access"},
        )
        _registered = True
        return oauth
