import asyncio
import json
import logging
import time
import traceback
from typing import Any

import httpx
import redis.asyncio as redis
from authlib.integrations.base_client.errors import OAuthError
from ctao_shared.config import get_settings
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_KEY_PREFIX,
    SESSION_REFRESH_TOKEN_KEY,
    SESSION_USER_ID_KEY,
)
from ctao_shared.db import decrypt_token, encrypt_token, get_redis_client
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict

from auth_service.metrics import TOKEN_REFRESH_FAILURES
from auth_service.oauth_client import oauth
from auth_service.security.csrf import ensure_xsrf_cookie, require_xsrf

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


def _settings():
    return get_settings()


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
) -> tuple[str, dict[str, Any]] | None:
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

    if not data.get(SESSION_USER_ID_KEY):
        return None

    return key, data


def _build_user_payload(
    session_data: dict[str, Any], iam_access_token: str | None
) -> dict[str, Any]:
    return {
        "app_user_id": session_data.get(SESSION_USER_ID_KEY),
        "iam_subject_id": session_data.get("iam_sub") or session_data.get("iam_subject_id"),
        "email": session_data.get("iam_email") or session_data.get("email"),
        "first_name": session_data.get("first_name") or session_data.get("given_name"),
        "last_name": session_data.get("last_name") or session_data.get("family_name"),
        "iam_access_token": iam_access_token,
        "is_active": True,
        "is_superuser": False,
    }


def _is_token_expired(expiry: float) -> bool:
    return (expiry - time.time()) <= 0


def _needs_refresh(expiry: float) -> bool:
    return (expiry - time.time()) < _settings().REFRESH_BUFFER_SECONDS


async def _attempt_refresh_once(refresh_token: str) -> dict[str, Any]:
    return await oauth.ctao.fetch_access_token(
        grant_type="refresh_token",
        refresh_token=refresh_token,
    )


async def _refresh_access_token_with_retry(refresh_token: str) -> dict[str, Any]:
    try:
        return await _attempt_refresh_once(refresh_token)
    except httpx.RequestError:
        await asyncio.sleep(0.2)
        return await _attempt_refresh_once(refresh_token)


def _apply_token_response(session_data: dict[str, Any], token_response: dict[str, Any]) -> str:
    new_at = token_response["access_token"]
    new_exp = token_response.get("expires_in", 3600)
    if _settings().OIDC_FAKE_EXPIRES_IN:
        new_exp = _settings().OIDC_FAKE_EXPIRES_IN

    session_data[SESSION_ACCESS_TOKEN_KEY] = new_at
    session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = time.time() + float(new_exp)

    # rotate refresh token if provided
    rt = token_response.get("refresh_token")
    if rt:
        new_enc = encrypt_token(rt)
        if new_enc:
            session_data[SESSION_REFRESH_TOKEN_KEY] = new_enc

    return new_at


async def _persist_session(
    redis_client: redis.Redis, key: str, session_data: dict[str, Any]
) -> None:
    await redis_client.setex(key, _settings().SESSION_DURATION_SECONDS, json.dumps(session_data))


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
    session_data: dict[str, Any],
) -> str | None:
    """
    Returns:
      - access token (possibly refreshed) if usable
      - None if re-auth is required (session deleted / invalid state)
    """
    at = session_data.get(SESSION_ACCESS_TOKEN_KEY)
    exp = session_data.get(SESSION_ACCESS_TOKEN_EXPIRY_KEY)

    if not at or exp is None:
        return None

    try:
        exp_f = float(exp)
    except (TypeError, ValueError):
        return None

    if _is_token_expired(exp_f):
        session_data[SESSION_ACCESS_TOKEN_KEY] = None
        session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = None
        await _persist_session(redis_client, key, session_data)
        return None

    if not _needs_refresh(exp_f):
        return at

    enc_rt = session_data.get(SESSION_REFRESH_TOKEN_KEY)
    if not enc_rt:
        await redis_client.delete(key)
        return None

    decrypted_rt = decrypt_token(enc_rt)
    if not decrypted_rt:
        await redis_client.delete(key)
        return None

    try:
        token_response = await _refresh_access_token_with_retry(decrypted_rt)
        at = _apply_token_response(session_data, token_response)
        await _persist_session(redis_client, key, session_data)
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

    key, session_data = loaded

    try:
        access_token = await _ensure_valid_access_token(redis, key, session_data)
        return _build_user_payload(session_data, access_token)

    except ReauthRequired:
        # Refresh failed
        await redis.delete(key)
        return None

    except Exception:
        # any unexpected error in auth path -> force re-auth
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
        logger.exception("ERROR in get_me constructing UserRead: %s", e)
        traceback.print_exc()
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
            int(user_session_data.get("app_user_id"))
            if user_session_data.get("app_user_id")
            else None
        ),
        first_name=first,
        last_name=last,
    )


@auth_api_router.post("/logout_session", tags=["auth"])
async def logout_session(
    request: Request,
    response: Response,
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, str]:
    # CSRF protection
    require_xsrf(request)

    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if session_id:
        await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")
        logger.info("Session %s deleted from Redis", session_id)

    # Clear cookies: session + xsrf
    response.delete_cookie(
        key=COOKIE_NAME_MAIN_SESSION,
        **get_settings().cookie_params,
    )
    delete_kwargs = {"path": "/"}
    if _settings().COOKIE_DOMAIN:
        delete_kwargs["domain"] = _settings().COOKIE_DOMAIN
    response.delete_cookie(key="XSRF-TOKEN", **delete_kwargs)
    return {"status": "logout successful"}


router = auth_api_router
