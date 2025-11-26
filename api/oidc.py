import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette.responses import Response

from .config import get_settings
from .constants import (
    COOKIE_NAME_MAIN_SESSION,
    CTAO_PROVIDER_NAME,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_KEY_PREFIX,
    SESSION_USER_ID_KEY,
)
from .db import encrypt_token, get_async_session, get_redis_client
from .models import UserRefreshToken, UserTable
from .oauth_client import oauth

logger = logging.getLogger(__name__)

settings = get_settings()
cookie_params = settings.cookie_params

oidc_router = APIRouter(prefix="/oidc", tags=["oidc"])


@oidc_router.get("/login")
async def login(request: Request) -> Response:
    """
    Start OIDC auth flow: redirect to provider.
    """
    redirect_uri: str = (
        settings.OIDC_REDIRECT_URI
        if not settings.PRODUCTION
        else f"{settings.BASE_URL}/api/oidc/callback"
    )
    logger.debug("OIDC login redirect_uri: %s", redirect_uri)
    resp = await oauth.ctao.authorize_redirect(request, redirect_uri)
    return cast(Response, resp)


@oidc_router.get("/callback")
async def auth_callback(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
    redis: redis.Redis = Depends(get_redis_client),
) -> Response:
    """
    Handle OIDC callback, create app session, and redirect to '/'.
    """
    try:
        token_response: dict[str, Any] = await oauth.ctao.authorize_access_token(request)
    except Exception as e:
        logger.exception("OIDC authorize_access_token failed")
        raise HTTPException(
            status_code=400, detail="OIDC authentication failed or was cancelled."
        ) from e

    userinfo = cast(dict[str, Any] | None, token_response.get("userinfo"))
    if not isinstance(userinfo, dict) or "sub" not in userinfo:
        raise HTTPException(
            status_code=400, detail="User identifier (sub) not found in OIDC token."
        )

    iam_subject_id: str = cast(str, userinfo["sub"])
    email: str | None = cast(str | None, userinfo.get("email"))
    given_name_to_store: str | None = cast(str | None, userinfo.get("given_name"))
    family_name_to_store: str | None = cast(str | None, userinfo.get("family_name"))

    if not (given_name_to_store and family_name_to_store):
        full_name_from_iam = userinfo.get("name")
        if isinstance(full_name_from_iam, str):
            parts = full_name_from_iam.strip().split(" ", 1)
            given_name_to_store = given_name_to_store or parts[0]
            family_name_to_store = family_name_to_store or (parts[1] if len(parts) > 1 else "")

    iam_access_token: str = cast(str, token_response["access_token"])
    iam_refresh_token: str | None = cast(str | None, token_response.get("refresh_token"))
    expires_in: int = cast(int, token_response.get("expires_in", 3600))
    if settings.OIDC_FAKE_EXPIRES_IN:
        expires_in = settings.OIDC_FAKE_EXPIRES_IN
    iam_access_token_expiry: float = time.time() + float(expires_in)

    # find or create minimal user in app db
    stmt = select(UserTable).where(UserTable.iam_subject_id == iam_subject_id)
    result = await db_session.execute(stmt)
    user_record = result.scalars().first()

    if not user_record:
        logger.info("Creating new minimal user for IAM sub: %s", iam_subject_id)
        user_record = UserTable(
            iam_subject_id=iam_subject_id,
            hashed_password="",
            is_active=True,
            is_verified=True,  # Verified by IAM
        )
        db_session.add(user_record)
        await db_session.flush()
        await db_session.refresh(user_record)

    app_user_id: int = int(user_record.id)

    # Store Refresh Token in DB (Encrypted)
    if iam_refresh_token:
        encrypted_rt = encrypt_token(iam_refresh_token)
        if encrypted_rt:
            rt_stmt = select(UserRefreshToken).where(
                UserRefreshToken.user_id == app_user_id,
                UserRefreshToken.iam_provider_name == CTAO_PROVIDER_NAME,
            )
            rt_result = await db_session.execute(rt_stmt)
            existing_rt_record = rt_result.scalars().first()
            if existing_rt_record:
                existing_rt_record.encrypted_refresh_token = encrypted_rt
                existing_rt_record.last_used_at = datetime.now(UTC)
                db_session.add(existing_rt_record)
            else:
                new_rt_record = UserRefreshToken(
                    user_id=app_user_id,
                    iam_provider_name=CTAO_PROVIDER_NAME,
                    encrypted_refresh_token=encrypted_rt,
                )
                db_session.add(new_rt_record)
            logger.info("Stored/Updated refresh token for user_id: %s", app_user_id)
        else:
            logger.warning("Failed to encrypt refresh token for user_id=%s", app_user_id)
    else:
        logger.warning("No refresh token received from IAM for user_id=%s", app_user_id)

    # Create Server-Side Session in Redis
    session_id = str(uuid.uuid4())
    session_data_to_store: dict[str, Any] = {
        SESSION_USER_ID_KEY: app_user_id,
        SESSION_IAM_SUB_KEY: iam_subject_id,
        SESSION_IAM_EMAIL_KEY: email,
        SESSION_IAM_GIVEN_NAME_KEY: given_name_to_store,
        SESSION_IAM_FAMILY_NAME_KEY: family_name_to_store,
        SESSION_ACCESS_TOKEN_KEY: iam_access_token,
        SESSION_ACCESS_TOKEN_EXPIRY_KEY: iam_access_token_expiry,
    }
    await redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        settings.SESSION_DURATION_SECONDS,
        json.dumps(session_data_to_store),
    )
    logger.info("Created Redis session %s for user_id: %s", session_id, app_user_id)

    # Commit DB changes
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        logger.exception("Error committing user/refresh token to DB: %s", e)
        raise HTTPException(status_code=500, detail="Failed to finalize user session setup.") from e

    # Set Session ID Cookie and Redirect
    response: RedirectResponse = RedirectResponse(url="/")
    response.set_cookie(
        key=COOKIE_NAME_MAIN_SESSION,
        value=session_id,
        max_age=settings.SESSION_DURATION_SECONDS,
        **cookie_params,
    )
    return response
