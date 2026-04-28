from __future__ import annotations

import json
import logging
import time
import uuid
from functools import lru_cache
from typing import Any, cast

import httpx
import redis.asyncio as redis
from authlib.integrations.starlette_client import OAuth
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_KEY_PREFIX,
    SESSION_REFRESH_TOKEN_KEY,
    SESSION_USER_ID_KEY,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette.responses import Response

from auth_service.config import get_auth_settings
from auth_service.crypto import encrypt_token
from auth_service.db import get_async_session
from auth_service.models import UserTable
from auth_service.oauth_client import get_oauth
from auth_service.redis_client import get_redis_client


class _OAuthProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_oauth(), name)


oauth = _OAuthProxy()


@lru_cache
def _settings():
    return get_auth_settings()


@lru_cache
def _oauth() -> OAuth:
    return get_oauth()


def _cookie_params() -> dict[str, Any]:
    return dict(_settings().cookie_params)


logger = logging.getLogger(__name__)


oidc_router = APIRouter(prefix="/oidc", tags=["oidc"])


class OIDCAuthError(HTTPException):
    pass


def _parse_userinfo(userinfo: Any) -> tuple[str, str | None, str | None, str | None]:
    if not isinstance(userinfo, dict) or "sub" not in userinfo:
        raise HTTPException(
            status_code=400, detail="User identifier (sub) not found in OIDC token."
        )

    iam_subject_id = str(userinfo["sub"])
    email = cast(str | None, userinfo.get("email"))
    given = cast(str | None, userinfo.get("given_name"))
    family = cast(str | None, userinfo.get("family_name"))

    if not (given and family):
        full = userinfo.get("name")
        if isinstance(full, str):
            parts = full.strip().split(" ", 1)
            given = given or (parts[0] if parts else None)
            family = family or (parts[1] if len(parts) > 1 else "")

    return iam_subject_id, email, given, family


def _compute_expiry(expires_in: Any) -> float:
    default_expires = 3600
    exp = int(expires_in or default_expires)
    fake = _settings().OIDC_FAKE_EXPIRES_IN
    if fake:
        exp = int(fake)
    return time.time() + float(exp)


async def _get_or_create_user(db_session: AsyncSession, iam_subject_id: str) -> int:
    stmt = select(UserTable).where(UserTable.iam_subject_id == iam_subject_id)
    result = await db_session.execute(stmt)
    user_record = result.scalars().first()

    if not user_record:
        logger.info("Creating new minimal user for IAM sub: %s", iam_subject_id)
        user_record = UserTable(
            iam_subject_id=iam_subject_id,
            hashed_password="",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user_record)
        await db_session.flush()
        await db_session.refresh(user_record)

    return int(user_record.id)


def _encrypt_refresh_token(rt: str | None) -> str | None:
    if not rt:
        return None
    enc = encrypt_token(rt)
    if not enc:
        logger.warning("Failed to encrypt refresh token; continuing without RT in session.")
        return None
    return enc


@oidc_router.get("/login")
async def login(request: Request) -> Response:
    """
    Start OIDC auth flow: redirect to provider.
    """
    redirect_uri = _settings().OIDC_REDIRECT_URI or (
        f"{_settings().BASE_URL}/auth/oidc/callback" if _settings().BASE_URL else None
    )
    if not redirect_uri:
        raise HTTPException(500, "OIDC_REDIRECT_URI (or BASE_URL) must be set.")
    try:
        resp = await _oauth().ctao.authorize_redirect(request, redirect_uri)
        return cast(Response, resp)
    except httpx.RequestError as err:
        logger.exception("OIDC provider metadata unreachable")
        raise HTTPException(status_code=503, detail="OIDC provider unreachable") from err


@oidc_router.get("/callback")
async def auth_callback(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
    redis: redis.Redis = Depends(get_redis_client),
) -> Response:
    """
    Handle OIDC callback, create app session, and redirect to '/'.
    Keeps existing behavior: authorize token, extract userinfo, upsert user,
    encrypt refresh token, store session JSON in Redis, commit DB, set cookie, redirect.
    """
    try:
        token_response: dict[str, Any] = await _oauth().ctao.authorize_access_token(request)
    except Exception as err:
        logger.exception("OIDC authorize_access_token failed")
        raise HTTPException(
            status_code=400,
            detail="OIDC authentication failed or was cancelled.",
        ) from err

    userinfo = cast(dict[str, Any] | None, token_response.get("userinfo"))
    iam_subject_id, email, given_name_to_store, family_name_to_store = _parse_userinfo(userinfo)

    iam_access_token: str = cast(str, token_response["access_token"])
    iam_refresh_token: str | None = cast(str | None, token_response.get("refresh_token"))
    iam_access_token_expiry: float = _compute_expiry(token_response.get("expires_in", 3600))

    app_user_id: int = await _get_or_create_user(db_session, iam_subject_id)

    encrypted_rt: str | None = _encrypt_refresh_token(iam_refresh_token)
    if iam_refresh_token is None:
        logger.warning("No refresh token received from IAM for user_id=%s", app_user_id)

    session_id = str(uuid.uuid4())
    session_data_to_store: dict[str, Any] = {
        SESSION_USER_ID_KEY: app_user_id,
        SESSION_IAM_SUB_KEY: iam_subject_id,
        SESSION_IAM_EMAIL_KEY: email,
        SESSION_IAM_GIVEN_NAME_KEY: given_name_to_store,
        SESSION_IAM_FAMILY_NAME_KEY: family_name_to_store,
        SESSION_ACCESS_TOKEN_KEY: iam_access_token,
        SESSION_ACCESS_TOKEN_EXPIRY_KEY: iam_access_token_expiry,
        SESSION_REFRESH_TOKEN_KEY: encrypted_rt,
    }

    await redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        _settings().SESSION_DURATION_SECONDS,
        json.dumps(session_data_to_store),
    )
    logger.info("Created Redis session %s for user_id: %s", session_id, app_user_id)

    try:
        await db_session.commit()
    except Exception as err:
        await db_session.rollback()
        logger.exception("Error committing user to DB: %s", err)
        raise HTTPException(
            status_code=500,
            detail="Failed to finalize user session setup.",
        ) from err

    redirect_target = _settings().FRONTEND_BASE_URL or _settings().BASE_URL or "/"
    response: RedirectResponse = RedirectResponse(url=redirect_target)
    response.set_cookie(
        key=COOKIE_NAME_MAIN_SESSION,
        value=session_id,
        max_age=_settings().SESSION_DURATION_SECONDS,
        **_cookie_params(),
    )
    return response
