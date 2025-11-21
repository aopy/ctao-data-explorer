from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_required_session_user
from .db import get_async_session


@dataclass
class CurrentUser:
    id: int
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    iam_subject_id: str | None = None
    iam_access_token: str | None = None


async def get_current_user(
    user_data: dict[str, Any] = Depends(get_required_session_user),
) -> CurrentUser:
    return CurrentUser(
        id=int(user_data["app_user_id"]),
        email=user_data.get("email"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        iam_subject_id=user_data.get("iam_subject_id"),
        iam_access_token=user_data.get("iam_access_token"),
    )


async def get_db(session: AsyncSession = Depends(get_async_session)) -> AsyncSession:
    return session
