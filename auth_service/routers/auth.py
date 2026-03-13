import json
import logging
import time
import traceback
from typing import Any

import redis.asyncio as redis
from ctao_shared.config import get_settings
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
from ctao_shared.db import decrypt_token, encrypt_token, get_redis_client
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict

from auth_service.oauth_client import oauth

logger = logging.getLogger(__name__)

settings = get_settings()
cookie_params = settings.cookie_params

REFRESH_BUFFER_SECONDS = settings.REFRESH_BUFFER_SECONDS


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


SESSION_DURATION_SECONDS = settings.SESSION_DURATION_SECONDS  # 8 hours


# Session-Based Authentication Dependency
async def get_current_session_user_data(
    request: Request,
    # db_session: AsyncSession = Depends(get_async_session),
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
                enc_rt = session_data.get(SESSION_REFRESH_TOKEN_KEY)
                if not enc_rt:
                    logger.info("No refresh token in session; keeping session without IAM token.")
                else:
                    decrypted_rt = decrypt_token(enc_rt)
                    if not decrypted_rt:
                        logger.warning(
                            "Failed to decrypt RT from session; keeping session without IAM token."
                        )
                        session_data[SESSION_REFRESH_TOKEN_KEY] = None
                        await redis.setex(key, SESSION_DURATION_SECONDS, json.dumps(session_data))
                    else:
                        try:
                            token_response = await oauth.ctao.fetch_access_token(
                                grant_type="refresh_token",
                                refresh_token=decrypted_rt,
                            )
                            new_at = token_response["access_token"]
                            new_exp = token_response.get("expires_in", 3600)
                            if settings.OIDC_FAKE_EXPIRES_IN:
                                new_exp = settings.OIDC_FAKE_EXPIRES_IN
                            new_at_exp = time.time() + float(new_exp)

                            session_data[SESSION_ACCESS_TOKEN_KEY] = new_at
                            session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = new_at_exp

                            # Refresh token rotation: store new RT if provided
                            if token_response.get("refresh_token"):
                                new_enc = encrypt_token(token_response["refresh_token"])
                                if new_enc:
                                    session_data[SESSION_REFRESH_TOKEN_KEY] = new_enc
                                else:
                                    logger.warning(
                                        "Failed to encrypt rotated refresh token; keeping old RT."
                                    )
                            await redis.setex(
                                key, SESSION_DURATION_SECONDS, json.dumps(session_data)
                            )
                            iam_access_token = new_at
                        except Exception:
                            logger.exception("IAM token refresh failed (keeping app session).")
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
    user_session_data: dict[str, Any] = Depends(get_required_session_user),
) -> MeResponse:
    """
    BFF-style 'who am I' endpoint.
    Returns an OIDC-like user profile derived from the server-side session.
    Tokens are never returned.
    """
    sub = (user_session_data.get("iam_subject_id") or "").strip()
    if not sub:
        raise HTTPException(status_code=401, detail="Not authenticated")

    first = (user_session_data.get("first_name") or "").strip() or None
    last = (user_session_data.get("last_name") or "").strip() or None

    full_name: str | None = None
    if first or last:
        full_name = " ".join([p for p in [first, last] if p])

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


@auth_api_router.post("/auth/logout_session", tags=["auth"])
async def logout_session(
    request: Request,
    response: Response,
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, str]:
    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if session_id:
        await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")
        logger.info("Session %s deleted from Redis", session_id)

    response.delete_cookie(key=COOKIE_NAME_MAIN_SESSION, **cookie_params)
    return {"status": "logout successful"}


router = auth_api_router
