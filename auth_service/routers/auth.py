import asyncio
import json
import logging
import time
from functools import lru_cache
from typing import Any, cast
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from cryptography.fernet import InvalidToken
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_KEY_PREFIX,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict

from auth_service.config import AuthSettings, get_auth_settings
from auth_service.crypto import decrypt_token, encrypt_token
from auth_service.metrics import TOKEN_REFRESH_FAILURES
from auth_service.oauth_client import get_oauth
from auth_service.redis_client import get_redis_client
from auth_service.security.csrf import ensure_xsrf_cookie, require_xsrf
from auth_service.session_data import SessionData


class _OAuthProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_oauth(), name)


oauth = _OAuthProxy()


@lru_cache
def _oauth() -> OAuth:
    return get_oauth()


logger = logging.getLogger(__name__)


# User Schemas
class UserRead(schemas.BaseUser[int]):
    id: int
    email: str
    iam_subject_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(schemas.BaseUserUpdate):
    email: str | None = None
    # No name updates


class MeResponse(BaseModel):
    sub: str
    name: str | None = None
    preferred_username: str | None = None
    email: str | None = None
    picture: str | None = None

    # optional app-specific fields
    app_user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None


class ReauthRequired(Exception):
    pass


@lru_cache
def _settings() -> AuthSettings:
    return get_auth_settings()


def _refresh_fail_reason(exc: Exception) -> str:
    # provider-side structured errors (Authlib)
    if isinstance(exc, OAuthError):
        err = getattr(exc, "error", None) or "oauth_error"
        # common iam token endpoint failures like,
        # invalid_grant = revoked/expired RT, bad code_verifier, etc.
        return str(err)

    # network/timeouts etc.
    if isinstance(exc, httpx.RequestError):
        return "network"

    return "other"


async def _load_session(
    redis_client: redis.Redis, request: Request
) -> tuple[str, SessionData] | None:
    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if not session_id:
        return None

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    raw = await redis_client.get(key)
    if not raw:
        return None

    await redis_client.expire(key, _settings().SESSION_DURATION_SECONDS)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid session data for session_id: %s", session_id)
        return None

    try:
        session = SessionData.from_redis_dict(data)
    except Exception:
        logger.warning("Session data schema invalid for session_id: %s", session_id, exc_info=True)
        return None

    # minimal validity: must have app_user_id
    if not session.app_user_id:
        return None

    return key, session


def _is_token_expired(expiry: float) -> bool:
    return (expiry - time.time()) <= 0


def _needs_refresh(expiry: float) -> bool:
    return (expiry - time.time()) < _settings().REFRESH_BUFFER_SECONDS


async def _attempt_refresh_once(refresh_token: str) -> dict[str, Any]:
    return await _oauth().ctao.fetch_access_token(
        grant_type="refresh_token",
        refresh_token=refresh_token,
    )


async def _refresh_access_token_with_retry(refresh_token: str) -> dict[str, Any]:
    try:
        return await _attempt_refresh_once(refresh_token)
    except httpx.RequestError:
        await asyncio.sleep(0.2)
        return await _attempt_refresh_once(refresh_token)


def _apply_token_response(session: SessionData, token_response: dict[str, Any]) -> str:
    new_at = token_response["access_token"]
    new_exp = token_response.get("expires_in", 3600)
    if _settings().OIDC_FAKE_EXPIRES_IN:
        new_exp = _settings().OIDC_FAKE_EXPIRES_IN

    session.iam_at = new_at
    session.iam_at_exp = time.time() + float(new_exp)

    rt = token_response.get("refresh_token")
    if rt:
        new_enc = encrypt_token(rt)
        if new_enc:
            session.iam_rt = new_enc

    return new_at


async def _persist_session(redis_client: redis.Redis, key: str, session: SessionData) -> None:
    await redis_client.setex(
        key,
        _settings().SESSION_DURATION_SECONDS,
        json.dumps(session.to_redis_dict()),
    )


async def _force_reauth(
    redis_client: redis.Redis, key: str, reason: str, exc: Exception | None = None
) -> None:
    TOKEN_REFRESH_FAILURES.labels(reason=reason).inc()
    logger.warning(
        "IAM token refresh failed (reason=%s). Forcing re-auth by deleting session.",
        reason,
        exc_info=exc is not None,
    )
    await redis_client.delete(key)


async def _ensure_valid_access_token(
    redis_client: redis.Redis,
    key: str,
    session: SessionData,
) -> str | None:
    at = session.iam_at
    exp = session.iam_at_exp

    if not at or exp is None:
        return None

    try:
        exp_f = float(exp)
    except (TypeError, ValueError):
        return None

    if _is_token_expired(exp_f):
        session.iam_at = None
        session.iam_at_exp = None
        await _persist_session(redis_client, key, session)
        return None

    if not _needs_refresh(exp_f):
        return at

    enc_rt = session.iam_rt
    if not enc_rt:
        await redis_client.delete(key)
        return None

    try:
        decrypted_rt = decrypt_token(enc_rt)
    except (InvalidToken, TypeError, ValueError):
        logger.warning(
            "Could not decrypt refresh token in session; forcing re-auth.", exc_info=True
        )
        await redis_client.delete(key)
        return None
    if not decrypted_rt:
        await redis_client.delete(key)
        return None

    try:
        token_response = await _refresh_access_token_with_retry(decrypted_rt)
        at = _apply_token_response(session, token_response)
        await _persist_session(redis_client, key, session)
        return at
    except Exception as e:
        reason = _refresh_fail_reason(e)
        await _force_reauth(redis_client, key, reason, exc=e)
        raise ReauthRequired() from e


async def get_current_session_user_data(
    request: Request,
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, Any] | None:
    loaded = await _load_session(redis, request)
    if not loaded:
        return None

    key, session = loaded

    try:
        access_token = await _ensure_valid_access_token(redis, key, session)

        # user_payload exposes iam_access_token for token relay use
        payload = session.user_payload()
        payload["iam_access_token"] = access_token  # ensure fresh token is used

        return payload

    except ReauthRequired:
        await redis.delete(key)
        return None

    except Exception:
        logger.exception("Unexpected error in session token handling; forcing re-auth.")
        await redis.delete(key)
        return None


# Dependency for required Authenticated User
async def get_required_session_user(
    user_data: dict[str, Any] | None = Depends(get_current_session_user_data),
) -> dict[str, Any]:
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_data


# Dependency for optional Authenticated User
async def get_optional_session_user(
    user_data: dict[str, Any] | None = Depends(get_current_session_user_data),
) -> dict[str, Any] | None:
    return user_data


# Router for User-related endpoints (e.g., /users/me)
auth_api_router = APIRouter()


@auth_api_router.get("/users/me_from_session", response_model=UserRead, tags=["users"])
async def get_me(
    request: Request,
    response: Response,
    user_session_data: dict[str, Any] = Depends(get_required_session_user),
) -> UserRead:
    ensure_xsrf_cookie(request, response)
    try:
        data_for_pydantic = {
            "id": user_session_data.get("app_user_id"),
            "email": user_session_data.get("email") or "",
            "first_name": user_session_data.get("first_name") or "",
            "last_name": user_session_data.get("last_name") or "",
            "iam_subject_id": user_session_data.get("iam_subject_id") or "",
            "is_active": user_session_data.get("is_active", True),
            "is_superuser": user_session_data.get("is_superuser", False),
            "is_verified": True,  # Assuming from IAM
        }

        validated_user = UserRead.model_validate(data_for_pydantic)
        return validated_user
    except Exception as e:
        logger.error("ERROR in get_me constructing UserRead: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating user response object.") from e


@auth_api_router.get("/me", response_model=MeResponse, tags=["users"])
async def me(
    request: Request,
    response: Response,
    user_session_data: dict[str, Any] = Depends(get_required_session_user),
) -> MeResponse:
    """
    BFF-style 'who am I' endpoint.
    Returns an OIDC-like user profile derived from the server-side session.
    Tokens are never returned.
    """
    # Set XSRF-TOKEN cookie on every /api/me response
    ensure_xsrf_cookie(request, response)

    sub = (user_session_data.get("iam_subject_id") or "").strip()
    if not sub:
        raise HTTPException(status_code=401, detail="Not authenticated")

    first = (user_session_data.get("first_name") or "").strip() or None
    last = (user_session_data.get("last_name") or "").strip() or None
    full_name = " ".join([p for p in [first, last] if p]) or None

    return MeResponse(
        sub=sub,
        name=full_name,
        preferred_username=None,
        email=(user_session_data.get("email") or None),
        picture=None,
        app_user_id=(
            int(cast(int, user_session_data["app_user_id"]))
            if user_session_data.get("app_user_id") is not None
            else None
        ),
        first_name=first,
        last_name=last,
    )


@lru_cache
def _oidc_metadata_url() -> str:
    metadata_url = (_settings().OIDC_SERVER_METADATA_URL or "").strip()
    if metadata_url:
        return metadata_url

    issuer = (_settings().OIDC_ISSUER or "").strip().rstrip("/")
    if issuer:
        return f"{issuer}/.well-known/openid-configuration"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="OIDC metadata URL is not configured.",
    )


async def _load_oidc_metadata() -> dict[str, Any]:
    url = _oidc_metadata_url()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as err:
        logger.warning("OIDC metadata endpoint unreachable: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC metadata endpoint unreachable.",
        ) from err
    except httpx.HTTPStatusError as err:
        logger.warning("OIDC metadata endpoint returned error: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC metadata endpoint returned an error.",
        ) from err
    except ValueError as err:
        logger.warning("OIDC metadata endpoint returned invalid JSON: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC metadata endpoint returned invalid JSON.",
        ) from err

    return cast(dict[str, Any], data)


async def _revoke_refresh_token(refresh_token: str, metadata: dict[str, Any]) -> None:
    revocation_endpoint = metadata.get("revocation_endpoint")
    if not revocation_endpoint:
        logger.warning("OIDC metadata does not expose revocation_endpoint; skipping RT revocation.")
        return

    data = {
        "token": refresh_token,
        "token_type_hint": "refresh_token",
    }

    client_id = _settings().CTAO_CLIENT_ID
    client_secret = _settings().CTAO_CLIENT_SECRET

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if client_id and client_secret:
                resp = await client.post(
                    str(revocation_endpoint),
                    data=data,
                    auth=(client_id, client_secret),
                )
            else:
                if client_id:
                    data["client_id"] = client_id
                resp = await client.post(
                    str(revocation_endpoint),
                    data=data,
                )
            if resp.status_code >= 400:
                logger.warning(
                    "Refresh-token revocation failed: status=%s body=%s",
                    resp.status_code,
                    resp.text[:500],
                )
                return

            logger.info("Refresh token revocation attempted successfully.")
    except httpx.RequestError:
        logger.warning("Refresh-token revocation endpoint unreachable.", exc_info=True)


def _post_logout_redirect_uri() -> str:
    return _settings().FRONTEND_BASE_URL or _settings().BASE_URL or "/"


def _build_end_session_url(
    metadata: dict[str, Any],
    *,
    id_token_hint: str | None,
) -> str | None:
    end_session_endpoint = (
        metadata.get("end_session_endpoint") or _settings().OIDC_END_SESSION_ENDPOINT
    )

    if not end_session_endpoint:
        logger.warning(
            "OIDC metadata does not expose end_session_endpoint and "
            "OIDC_END_SESSION_ENDPOINT is not configured; no upstream logout URL."
        )
        return None

    params: dict[str, str] = {
        "post_logout_redirect_uri": _post_logout_redirect_uri(),
    }

    if id_token_hint:
        params["id_token_hint"] = id_token_hint

    if _settings().CTAO_CLIENT_ID:
        params["client_id"] = _settings().CTAO_CLIENT_ID

    return f"{end_session_endpoint}?{urlencode(params)}"


@auth_api_router.post("/logout_session", tags=["auth"])
async def logout_session(
    request: Request,
    response: Response,
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, str | None]:
    require_xsrf(request)

    metadata: dict[str, Any] = {}
    session: SessionData | None = None
    session_key: str | None = None

    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if session_id:
        session_key = f"{SESSION_KEY_PREFIX}{session_id}"
        raw = await redis.get(session_key)

        if raw:
            try:
                raw_text = raw.decode() if isinstance(raw, bytes) else raw
                session = SessionData.from_redis_dict(json.loads(raw_text))
            except Exception:
                logger.warning(
                    "Could not parse session during logout for session_id=%s",
                    session_id,
                    exc_info=True,
                )

    try:
        metadata = await _load_oidc_metadata()
    except HTTPException:
        logger.warning("Could not load OIDC metadata during logout; continuing local logout.")
        metadata = {}

    refresh_token: str | None = None
    if session and session.iam_rt:
        try:
            refresh_token = decrypt_token(session.iam_rt)
        except (InvalidToken, TypeError, ValueError):
            logger.warning(
                "Could not decrypt refresh token during logout for session_id=%s; skipping revocation.",
                session_id,
                exc_info=True,
            )
            refresh_token = None

        if refresh_token:
            await _revoke_refresh_token(refresh_token, metadata)

    logout_url = _build_end_session_url(
        metadata,
        id_token_hint=session.iam_id_token if session else None,
    )

    if session_key:
        await redis.delete(session_key)
        logger.info("Session %s deleted from Redis", session_id)

    cookie_params = get_auth_settings().cookie_params
    response.delete_cookie(
        key=COOKIE_NAME_MAIN_SESSION,
        path=cookie_params.get("path", "/"),
        domain=cookie_params.get("domain") or None,
    )
    response.delete_cookie(
        key="XSRF-TOKEN",
        path="/",
        domain=_settings().COOKIE_DOMAIN or None,
    )

    return {
        "status": "logout successful",
        "logout_url": logout_url,
    }


router = auth_api_router
