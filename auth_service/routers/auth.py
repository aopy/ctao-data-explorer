import json
import logging
import time
import traceback
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from ctao_shared.config import get_settings
from ctao_shared.constants import (
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
from ctao_shared.db import decrypt_token, encrypt_token, get_async_session, get_redis_client
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_users import schemas
from pydantic import ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth_service.models import UserRefreshToken
from auth_service.oauth_client import oauth

logger = logging.getLogger(__name__)

settings = get_settings()
cookie_params = settings.cookie_params

REFRESH_BUFFER_SECONDS = settings.REFRESH_BUFFER_SECONDS


# User Schemas
class UserRead(schemas.BaseUser[int]):
    id: int
    # email: str | None = None
    email: str
    iam_subject_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(schemas.BaseUserUpdate):
    email: str | None = None
    # No name updates


SESSION_DURATION_SECONDS = settings.SESSION_DURATION_SECONDS  # 8 hours


# Session-Based Authentication Dependency
async def get_current_session_user_data(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, Any] | None:
    # Read cookie via constant
    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if not session_id:
        return None

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    session_data_json = await redis.get(key)
    if not session_data_json:
        return None

    # keep Redis entry alive
    await redis.expire(key, SESSION_DURATION_SECONDS)

    try:
        session_data = json.loads(session_data_json)
    except json.JSONDecodeError:
        logger.warning("Invalid session data for session_id: %s", session_id)
        return None

    app_user_id = session_data.get(SESSION_USER_ID_KEY)
    if not app_user_id:
        # minimal requirement for being "logged in" to the app
        return None

    # IAM token is optional for app auth, handle it leniently
    iam_access_token = session_data.get(SESSION_ACCESS_TOKEN_KEY)
    iam_access_token_expiry = session_data.get(SESSION_ACCESS_TOKEN_EXPIRY_KEY)

    try:
        if iam_access_token and iam_access_token_expiry:
            remaining = iam_access_token_expiry - time.time()

            if remaining <= 0:
                # expire IAM token but DO NOT drop the app session
                session_data[SESSION_ACCESS_TOKEN_KEY] = None
                session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = None
                await redis.setex(key, SESSION_DURATION_SECONDS, json.dumps(session_data))
                iam_access_token = None

            elif remaining < REFRESH_BUFFER_SECONDS:
                # Try to refresh; on failure, keep session intact
                stmt = select(UserRefreshToken).where(
                    UserRefreshToken.user_id == app_user_id,
                    UserRefreshToken.iam_provider_name == CTAO_PROVIDER_NAME,
                )
                result = await db_session.execute(stmt)
                user_rt_record = result.scalars().first()

                if user_rt_record and user_rt_record.encrypted_refresh_token:
                    decrypted_rt = decrypt_token(user_rt_record.encrypted_refresh_token)
                    if decrypted_rt:
                        try:
                            token_response = await oauth.ctao.fetch_access_token(
                                grant_type="refresh_token",
                                refresh_token=decrypted_rt,
                            )
                            new_at = token_response["access_token"]
                            new_exp = token_response.get("expires_in", 3600)
                            if settings.OIDC_FAKE_EXPIRES_IN:
                                new_exp = settings.OIDC_FAKE_EXPIRES_IN
                            new_at_exp = time.time() + new_exp

                            if "refresh_token" in token_response:
                                enc = encrypt_token(token_response["refresh_token"])
                                if enc is not None:
                                    user_rt_record.encrypted_refresh_token = enc
                                user_rt_record.last_used_at = datetime.now(UTC)
                                db_session.add(user_rt_record)

                            session_data[SESSION_ACCESS_TOKEN_KEY] = new_at
                            session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = new_at_exp
                            await redis.setex(
                                key, SESSION_DURATION_SECONDS, json.dumps(session_data)
                            )
                            iam_access_token = new_at
                        except Exception:
                            logger.exception("IAM token refresh failed (keeping app session).")
                    else:
                        logger.warning(
                            "Failed to decrypt RT; keeping app session without IAM token."
                        )
                else:
                    logger.info("No RT on file; keeping app session without IAM token.")
    except Exception:
        logger.exception("Non-fatal error in session token handling; preserving session.")

    iam_subject_id = (
        session_data.get(SESSION_IAM_SUB_KEY)
        or session_data.get("iam_subject_id")
        or session_data.get("sub")
    )
    email = session_data.get(SESSION_IAM_EMAIL_KEY) or session_data.get("email")
    first_name = (
        session_data.get(SESSION_IAM_GIVEN_NAME_KEY)
        or session_data.get("given_name")
        or session_data.get("first_name")
    )
    last_name = (
        session_data.get(SESSION_IAM_FAMILY_NAME_KEY)
        or session_data.get("family_name")
        or session_data.get("last_name")
    )

    return {
        "app_user_id": app_user_id,
        "iam_subject_id": iam_subject_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "iam_access_token": iam_access_token,
        "is_active": True,
        "is_superuser": False,
    }


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
    user_session_data: dict[str, Any] = Depends(get_required_session_user),
) -> UserRead:
    # print("DEBUG get_me: user_session_data received:", user_session_data)
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


# Logout Endpoint (uses new session logic)
@auth_api_router.post("/auth/logout_session", tags=["auth"])
async def logout_session(
    request: Request,
    response: Response,  # Keep Response for cookie clearing
    redis: redis.Redis = Depends(get_redis_client),
    # Optional: get user_id for RT deletion
    user_session_data: dict[str, Any] | None = Depends(get_optional_session_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    session_id = request.cookies.get("ctao_session_main")
    if session_id:
        await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")
        logger.info("Session %s deleted from Redis", session_id)

        if user_session_data and user_session_data.get("app_user_id"):
            app_user_id = user_session_data["app_user_id"]
            # Delete refresh token from DB
            stmt = select(UserRefreshToken).where(UserRefreshToken.user_id == app_user_id)
            result = await db_session.execute(stmt)
            rt_to_delete = result.scalars().all()
            for rt_rec in rt_to_delete:
                await db_session.delete(rt_rec)
            await db_session.commit()
            logger.info("Refresh token(s) for user %s deleted from DB", app_user_id)
            # TODO: Optionally call IAM token revocation endpoint with the RT if we had it

    # Clear the session cookie from the browser
    cookie_name = COOKIE_NAME_MAIN_SESSION
    response.delete_cookie(
        key=cookie_name,
        # path="/",
        # domain=config_env("COOKIE_DOMAIN", default=None) if PRODUCTION else None,
        # secure=config_env("COOKIE_SECURE", cast=bool, default=False) if PRODUCTION else False,
        # httponly=True,
        # samesite="lax"
        # samesite = "none"
        # max_age=0,
        **cookie_params,
    )
    return {"status": "logout successful"}


router = auth_api_router
