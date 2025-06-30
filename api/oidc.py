from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# from authlib.integrations.starlette_client import OAuth
from .oauth_client import oauth, CTAO_PROVIDER_NAME
from starlette.config import Config as StarletteConfig
import json
import time
import uuid
from datetime import datetime

from .db import get_async_session, get_redis_client, encrypt_token
from .models import UserTable, UserRefreshToken
from .auth import (
    SESSION_KEY_PREFIX, SESSION_USER_ID_KEY, SESSION_IAM_SUB_KEY,
    SESSION_IAM_EMAIL_KEY, SESSION_ACCESS_TOKEN_KEY,
    SESSION_ACCESS_TOKEN_EXPIRY_KEY, SESSION_DURATION_SECONDS,
    PRODUCTION, SESSION_IAM_GIVEN_NAME_KEY, SESSION_IAM_FAMILY_NAME_KEY
)
import redis.asyncio as redis


config_env = StarletteConfig('.env')

oidc_router = APIRouter(prefix="/oidc", tags=["oidc"])

@oidc_router.get("/login")
async def login(request: Request):
    redirect_uri = config_env("OIDC_REDIRECT_URI", default="http://localhost:8000/api/oidc/callback")
    base_url_env = config_env("BASE_URL", default=None)
    if PRODUCTION and base_url_env:
        redirect_uri = f"{base_url_env}/api/oidc/callback"

    print(f"DEBUG OIDC Login: Using redirect_uri: {redirect_uri}")
    # Store state in Starlette's temporary session (ctao_session_temp)
    return await oauth.ctao.authorize_redirect(request, redirect_uri)


@oidc_router.get("/callback")
async def auth_callback(
        request: Request,
        db_session: AsyncSession = Depends(get_async_session),
        redis: redis.Redis = Depends(get_redis_client),
):
    try:
        # This uses the temporary OIDC state session cookie
        token_response = await oauth.ctao.authorize_access_token(request)
    except Exception as e:
        print(f"OIDC Error during authorize_access_token: {e}")
        # import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail="OIDC authentication failed or was cancelled.")

    userinfo = token_response.get('userinfo')
    if not userinfo or not userinfo.get('sub'):
        raise HTTPException(status_code=400, detail="User identifier (sub) not found in OIDC token.")

    iam_subject_id = userinfo['sub']
    email = userinfo.get('email')
    full_name_from_iam = userinfo.get('name')
    given_name_to_store = None
    family_name_to_store = None

    if full_name_from_iam and isinstance(full_name_from_iam, str):
        name_parts = full_name_from_iam.strip().split(' ', 1)
        given_name_to_store = name_parts[0]
        if len(name_parts) > 1:
            family_name_to_store = name_parts[1]
        else:
            family_name_to_store = ""
    # print(f"DEBUG OIDC Callback: UserInfo from IAM: {userinfo}")
    # print(f"DEBUG OIDC Callback: Parsed given_name: {given_name_to_store}, family_name: {family_name_to_store}")


    iam_access_token = token_response['access_token']
    iam_refresh_token = token_response.get('refresh_token')
    expires_in = token_response.get('expires_in', 3600) # Default to 1 hour
    fake_exp = StarletteConfig('.env')('OIDC_FAKE_EXPIRES_IN', cast=int, default=None)
    if fake_exp:
        expires_in = fake_exp
    iam_access_token_expiry = time.time() + expires_in

    # find or create minimal user in app db
    stmt = select(UserTable).where(UserTable.iam_subject_id == iam_subject_id)
    result = await db_session.execute(stmt)
    user_record = result.scalars().first()

    if not user_record:
        print(f"Creating new minimal user for IAM sub: {iam_subject_id}")
        user_record = UserTable(
            iam_subject_id=iam_subject_id,
            # email=email,
            hashed_password="",
            is_active=True,
            is_verified=True # Verified by IAM
        )
        db_session.add(user_record)
        await db_session.flush()
        await db_session.refresh(user_record)
    #elif email and user_record.email != email:
    #    user_record.email = email
    #    db_session.add(user_record)
    #    await db_session.flush()
    #    await db_session.refresh(user_record)

    app_user_id = user_record.id

    # Store Refresh Token in DB (Encrypted)
    if iam_refresh_token:
        encrypted_rt = encrypt_token(iam_refresh_token)
        if encrypted_rt:
            rt_stmt = select(UserRefreshToken).where(
                UserRefreshToken.user_id == app_user_id,
                UserRefreshToken.iam_provider_name == CTAO_PROVIDER_NAME
            )
            rt_result = await db_session.execute(rt_stmt)
            existing_rt_record = rt_result.scalars().first()
            if existing_rt_record:
                existing_rt_record.encrypted_refresh_token = encrypted_rt
                existing_rt_record.last_used_at = datetime.utcnow() # or creation time
                db_session.add(existing_rt_record)
            else:
                new_rt_record = UserRefreshToken(
                    user_id=app_user_id,
                    iam_provider_name=CTAO_PROVIDER_NAME,
                    encrypted_refresh_token=encrypted_rt
                )
                db_session.add(new_rt_record)
            print(f"Stored/Updated refresh token for user_id: {app_user_id}")
        else:
            print(f"WARNING: Failed to encrypt refresh token for user_id: {app_user_id}")
    else:
        print(f"WARNING: No refresh token received from IAM for user_id: {app_user_id}")


    # Create Server-Side Session in Redis
    session_id = str(uuid.uuid4()) # Generate a secure random session ID
    session_data_to_store = {
        SESSION_USER_ID_KEY: app_user_id,
        SESSION_IAM_SUB_KEY: iam_subject_id,
        SESSION_IAM_EMAIL_KEY: email, # Optional
        SESSION_IAM_GIVEN_NAME_KEY: given_name_to_store,
        SESSION_IAM_FAMILY_NAME_KEY: family_name_to_store,
        SESSION_ACCESS_TOKEN_KEY: iam_access_token,
        SESSION_ACCESS_TOKEN_EXPIRY_KEY: iam_access_token_expiry,
    }
    await redis.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        SESSION_DURATION_SECONDS, # Session TTL in Redis
        json.dumps(session_data_to_store)
    )
    print(f"Created Redis session {session_id} for user_id: {app_user_id}")

    # Commit DB changes
    try:
        await db_session.commit()
    except Exception as db_exc:
        await db_session.rollback()
        print(f"Error committing user/refresh token to DB: {db_exc}")
        raise HTTPException(status_code=500, detail="Failed to finalize user session setup.")


    # Set Session ID Cookie and Redirect
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="ctao_session_main",
        value=session_id,
        max_age=SESSION_DURATION_SECONDS, # Match Redis TTL
        path="/",
        domain=config_env("COOKIE_DOMAIN", default=None) if PRODUCTION else None,
        secure=config_env("COOKIE_SECURE", cast=bool, default=False) if PRODUCTION else False,
        httponly=True,
        samesite="lax"
    )
    return response
