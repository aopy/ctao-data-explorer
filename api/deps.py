from dataclasses import dataclass
from typing import Optional, Dict, Any
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session
from .auth import get_required_session_user

@dataclass
class CurrentUser:
    id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    iam_subject_id: Optional[str] = None
    iam_access_token: Optional[str] = None

async def get_current_user(
    user_data: Dict[str, Any] = Depends(get_required_session_user)
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
