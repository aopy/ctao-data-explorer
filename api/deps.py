from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.deps import get_required_identity
from api.auth.jwt_verifier import VerifiedIdentity
from api.db import get_async_session


@dataclass
class CurrentUser:
    sub: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None


async def get_current_user(
    identity: VerifiedIdentity = Depends(get_required_identity),
) -> CurrentUser:
    return CurrentUser(
        sub=identity.sub,
        email=identity.email,
        first_name=identity.given_name,
        last_name=identity.family_name,
    )


async def get_db(session: AsyncSession = Depends(get_async_session)) -> AsyncSession:
    return session


def get_current_user_with_sub(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# alias for existing imports
get_current_user_with_iam_sub = get_current_user_with_sub
