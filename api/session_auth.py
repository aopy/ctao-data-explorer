import json
import logging
from typing import Any

import redis.asyncio as redis
from ctao_shared.config import get_settings
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_KEY_PREFIX,
    SESSION_USER_ID_KEY,
)
from ctao_shared.db import get_redis_client
from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_current_session_user_data(
    request: Request,
    redis: redis.Redis = Depends(get_redis_client),
) -> dict[str, Any] | None:
    session_id = request.cookies.get(COOKIE_NAME_MAIN_SESSION)
    if not session_id:
        return None

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    session_data_json = await redis.get(key)
    if not session_data_json:
        return None

    # keep session alive
    await redis.expire(key, settings.SESSION_DURATION_SECONDS)

    try:
        session_data = json.loads(session_data_json)
    except json.JSONDecodeError:
        logger.warning("Invalid session data for session_id: %s", session_id)
        return None

    app_user_id = session_data.get(SESSION_USER_ID_KEY)
    if not app_user_id:
        return None

    return {
        "app_user_id": app_user_id,
        "iam_subject_id": session_data.get(SESSION_IAM_SUB_KEY),
        "email": session_data.get(SESSION_IAM_EMAIL_KEY),
        "first_name": session_data.get(SESSION_IAM_GIVEN_NAME_KEY),
        "last_name": session_data.get(SESSION_IAM_FAMILY_NAME_KEY),
        "iam_access_token": session_data.get(SESSION_ACCESS_TOKEN_KEY),
        "is_active": True,
        "is_superuser": False,
    }


async def get_required_session_user(
    user_data: dict[str, Any] | None = Depends(get_current_session_user_data),
) -> dict[str, Any]:
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_data


async def get_optional_session_user(
    user_data: dict[str, Any] | None = Depends(get_current_session_user_data),
) -> dict[str, Any] | None:
    return user_data
