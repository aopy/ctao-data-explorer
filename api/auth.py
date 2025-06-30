from fastapi import APIRouter, Depends, Response, HTTPException, status, Request
from fastapi_users import FastAPIUsers
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy
)
from starlette.config import Config
from fastapi_users import schemas
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .db import get_async_session, get_redis_client, encrypt_token, decrypt_token
from .models import UserTable, UserRefreshToken
# from authlib.integrations.starlette_client import OAuth
from .oauth_client import oauth, CTAO_PROVIDER_NAME
from starlette.config import Config as StarletteConfig
import json
import time
from typing import Optional, Dict, Any
from fastapi_users.manager import BaseUserManager
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import traceback


config_env = StarletteConfig(".env")

PRODUCTION = config_env("BASE_URL", default="") is not None

# User Schemas
class UserRead(schemas.BaseUser[int]):
    id: int
    email: Optional[str] = None
    iam_subject_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    # is_active: bool # From fastapi-users BaseUser

    class Config:
        from_attributes = True

class UserUpdate(schemas.BaseUserUpdate):
    email: Optional[str] = None
    # No name updates

# Constants for session
SESSION_KEY_PREFIX = "user_session:"
SESSION_USER_ID_KEY = "app_user_id"
SESSION_IAM_SUB_KEY = "iam_sub"
SESSION_IAM_EMAIL_KEY = "iam_email"
SESSION_IAM_GIVEN_NAME_KEY = "first_name"
SESSION_IAM_FAMILY_NAME_KEY = "last_name"
SESSION_ACCESS_TOKEN_KEY = "iam_at" # Key for storing IAM Access Token in session
SESSION_ACCESS_TOKEN_EXPIRY_KEY = "iam_at_exp"
SESSION_DURATION_SECONDS = config_env("SESSION_DURATION_SECONDS", cast=int, default=3600 * 8) # 8 hours


# Session-Based Authentication Dependency
async def get_current_session_user_data(
        request: Request,
        db_session: AsyncSession = Depends(get_async_session),  # For DB operations
        redis: redis.Redis = Depends(get_redis_client)  # For session store
) -> Optional[Dict[str, Any]]:  # Returns dict with user data or None
    session_id = request.cookies.get("ctao_session_main")
    if not session_id:
        return None

    session_data_json = await redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    if not session_data_json:
        return None

    # keep the Redis entry alive as long as the user is active
    await redis.expire(f"{SESSION_KEY_PREFIX}{session_id}", SESSION_DURATION_SECONDS)

    try:
        session_data = json.loads(session_data_json)
        # print("DEBUG: Raw session data from Redis:", session_data)
    except json.JSONDecodeError:
        print(f"Error decoding session data for session_id: {session_id}")
        return None  # Invalid session data

    app_user_id = session_data.get(SESSION_USER_ID_KEY)
    iam_access_token = session_data.get(SESSION_ACCESS_TOKEN_KEY)
    iam_access_token_expiry = session_data.get(SESSION_ACCESS_TOKEN_EXPIRY_KEY)

    if not app_user_id or not iam_access_token or not iam_access_token_expiry:
        print(f"Incomplete session data for app_user_id: {app_user_id}")
        return None  # Essential data missing

    # Check Access Token Expiry (give a small buffer, e.g., 60 seconds)
    if time.time() >= (iam_access_token_expiry - 60):
        print(f"IAM Access Token expired for user {app_user_id}. Attempting refresh.")
        # Refresh Logic
        stmt = select(UserRefreshToken).where(
            UserRefreshToken.user_id == app_user_id,
            UserRefreshToken.iam_provider_name == CTAO_PROVIDER_NAME
        )
        result = await db_session.execute(stmt)
        user_rt_record = result.scalars().first()

        if not user_rt_record or not user_rt_record.encrypted_refresh_token:
            print(f"No valid refresh token found for user {app_user_id}. Clearing session.")
            await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")  # Delete invalid session
            return None

        decrypted_rt = decrypt_token(user_rt_record.encrypted_refresh_token)
        if not decrypted_rt:
            print(f"Failed to decrypt refresh token for user {app_user_id}. Clearing session.")
            await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")
            return None

        try:
            # Ensure oauth.ctao client is available
            if not hasattr(oauth, CTAO_PROVIDER_NAME):
                raise Exception(f"OIDC provider '{CTAO_PROVIDER_NAME}' not configured in oauth object for refresh.")

            # Use authlib to refresh the token
            token_response = await oauth.ctao.fetch_access_token(
                grant_type='refresh_token',
                refresh_token=decrypted_rt,
            )
            print(f"DEBUG: Refresh token response: {token_response}")

            new_iam_access_token = token_response['access_token']
            # new_iam_access_token_expiry = time.time() + token_response['expires_in']
            new_exp = token_response.get('expires_in', 3600)
            fake_exp = StarletteConfig('.env')('OIDC_FAKE_EXPIRES_IN', cast=int, default=None)
            if fake_exp:
                new_exp = fake_exp
            new_iam_access_token_expiry = time.time() + new_exp
            # Update stored refresh token if a new one is issued
            if 'refresh_token' in token_response:
                new_decrypted_rt = token_response['refresh_token']
                user_rt_record.encrypted_refresh_token = encrypt_token(new_decrypted_rt)
                user_rt_record.last_used_at = datetime.utcnow()  # Should be timezone aware
                db_session.add(user_rt_record)

            # Update session data in Redis
            session_data[SESSION_ACCESS_TOKEN_KEY] = new_iam_access_token
            session_data[SESSION_ACCESS_TOKEN_EXPIRY_KEY] = new_iam_access_token_expiry
            await redis.setex(
                f"{SESSION_KEY_PREFIX}{session_id}",
                SESSION_DURATION_SECONDS,
                json.dumps(session_data)
            )
            print(f"Successfully refreshed IAM Access Token for user {app_user_id}")
            iam_access_token = new_iam_access_token  # Use the new token for this request

        except Exception as refresh_exc:
            print(f"ERROR: Refresh token grant failed for user {app_user_id}: {refresh_exc}")
            # import traceback; traceback.print_exc()
            await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")  # Delete invalid session
            # delete the refresh token from DB if it's definitively invalid
            # await db_session.delete(user_rt_record)
            return None
        finally:
            pass

    return {
        "app_user_id": app_user_id,
        "iam_subject_id": session_data.get(SESSION_IAM_SUB_KEY),
        "email": session_data.get(SESSION_IAM_EMAIL_KEY),
        "first_name": session_data.get(SESSION_IAM_GIVEN_NAME_KEY),
        "last_name": session_data.get(SESSION_IAM_FAMILY_NAME_KEY),
        "iam_access_token": iam_access_token,
        "is_active": True,
        "is_superuser": False
    }


# Dependency for required Authenticated User
async def get_required_session_user(
        user_data: Optional[Dict[str, Any]] = Depends(get_current_session_user_data)
) -> Dict[str, Any]:
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_data


# Dependency for optional Authenticated User
async def get_optional_session_user(
        user_data: Optional[Dict[str, Any]] = Depends(get_current_session_user_data)
) -> Optional[Dict[str, Any]]:
    return user_data


# Router for User-related endpoints (e.g., /users/me)
auth_api_router = APIRouter()


@auth_api_router.get("/users/me_from_session", response_model=UserRead, tags=["users"])
async def get_me(
        user_session_data: Dict[str, Any] = Depends(get_required_session_user),
):
    # print("DEBUG get_me: user_session_data received:", user_session_data)
    try:
        data_for_pydantic = {
            "id": user_session_data.get("app_user_id"),
            "email": user_session_data.get("email"),
            "first_name": user_session_data.get("first_name"),
            "last_name": user_session_data.get("last_name"),
            "iam_subject_id": user_session_data.get("iam_subject_id"),
            "is_active": user_session_data.get("is_active", True),
            "is_superuser": user_session_data.get("is_superuser", False),
            "is_verified": True  # Assuming from IAM
        }

        validated_user = UserRead.model_validate(data_for_pydantic)
        # print(f"DEBUG get_me: Returning validated UserRead: {validated_user.model_dump_json(indent=2)}")
        return validated_user
    except Exception as e:
        print(f"ERROR in get_me constructing UserRead: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error creating user response object.")


# Logout Endpoint (uses new session logic)
@auth_api_router.post("/auth/logout_session", tags=["auth"])
async def logout_session(
        request: Request,
        response: Response,  # Keep Response for cookie clearing
        redis: redis.Redis = Depends(get_redis_client),
        # Optional: get user_id for RT deletion
        user_session_data: Optional[Dict[str, Any]] = Depends(get_optional_session_user),
        db_session: AsyncSession = Depends(get_async_session)
):
    session_id = request.cookies.get("ctao_session_main")
    if session_id:
        await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")
        print(f"Session {session_id} deleted from Redis.")

        if user_session_data and user_session_data.get("app_user_id"):
            app_user_id = user_session_data["app_user_id"]
            # Delete refresh token from DB
            stmt = select(UserRefreshToken).where(UserRefreshToken.user_id == app_user_id)
            result = await db_session.execute(stmt)
            rt_to_delete = result.scalars().all()
            for rt_rec in rt_to_delete:
                await db_session.delete(rt_rec)
            await db_session.commit()
            print(f"Refresh token(s) for user {app_user_id} deleted from DB.")
            # TODO: Optionally call IAM token revocation endpoint with the RT if we had it

    # Clear the session cookie from the browser
    cookie_name = "ctao_session_main"
    response.delete_cookie(
        key=cookie_name,
        path="/",
        domain=config_env("COOKIE_DOMAIN", default=None) if PRODUCTION else None,
        secure=config_env("COOKIE_SECURE", cast=bool, default=False) if PRODUCTION else False,
        httponly=True,
        samesite="lax"
    )
    return {"status": "logout successful"}

router = auth_api_router
