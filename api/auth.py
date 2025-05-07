from fastapi import APIRouter, Depends, Response, HTTPException, status
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
from .db import get_async_session
from .models import UserTable
from fastapi_users.manager import BaseUserManager
from datetime import datetime
from fastapi.responses import JSONResponse
import os

PRODUCTION = os.getenv("BASE_URL") is not None

# User Schemas
class UserRead(schemas.BaseUser[int]):
    first_name: str | None = None
    last_name: str | None = None
    first_login_at: datetime | None = None
    email: str
    class Config:
        from_attributes = True

# class UserCreate(schemas.BaseUserCreate):
#    first_name: str | None = None
#    last_name: str | None = None

class UserUpdate(schemas.BaseUserUpdate):
    first_name: str | None = None
    last_name: str | None = None

# JWT Secret from .env
config = Config(".env")
JWT_SECRET = config("JWT_SECRET", default="CHANGE_ME_PLEASE")

class UserManager(BaseUserManager[UserTable, int]):
    reset_password_token_secret = JWT_SECRET
    verification_token_secret = JWT_SECRET
    def parse_id(self, user_id: str) -> int:
        return int(user_id)

async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> SQLAlchemyUserDatabase[UserTable, int]:
    yield SQLAlchemyUserDatabase(session, UserTable)

async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[UserTable, int] = Depends(get_user_db),
) -> UserManager:
    yield UserManager(user_db)


# Configure Cookie Transport
cookie_transport = CookieTransport(
    cookie_name="ctao_access_token",
    cookie_max_age=3600,
    cookie_path="/",
    cookie_secure=False, # PRODUCTION
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_domain="ctao-data-explorer.obspm.fr" if PRODUCTION else None,
)

# JWT Strategy
def get_jwt_strategy() -> JWTStrategy:
    """Create a JWT strategy with the secret loaded from .env."""
    return JWTStrategy(secret=JWT_SECRET, lifetime_seconds=3600)

# Authentication Backend: Use CookieTransport
auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI-Users setup
fastapi_users = FastAPIUsers[UserTable, int](
    get_user_manager,
    [auth_backend],
)

# User Dependency
# This will extract the user from the cookie via the transport
current_active_user = fastapi_users.current_user(active=True)

current_optional_active_user = fastapi_users.current_user(active=True, optional=True)

# Routes
auth_router = APIRouter()

@auth_router.post("/auth/logout", tags=["auth"])
async def logout(
    response: Response,
    user: UserTable = Depends(current_active_user),
    transport: CookieTransport = Depends(lambda: cookie_transport),
) -> Response:
    """
    Logout user by returning a response that clears the authentication cookie.
    """
    try:
        success_content = {"status": "logout successful"}
        logout_response = await transport.get_logout_response()
        final_response = JSONResponse(content=success_content)
        cookie_header = logout_response.headers.get("set-cookie")

        if cookie_header:
            final_response.headers["set-cookie"] = cookie_header
        else:
             print("WARNING: get_logout_response did not return a Set-Cookie header.")

        return final_response

    except Exception as e:
        print(f"Error during transport logout: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout."
        )

@auth_router.post("/api/auth/logout", include_in_schema=False)
async def logout_alias(response: Response,
                       user: UserTable = Depends(current_active_user),
                       transport: CookieTransport = Depends(lambda: cookie_transport)):
    return await logout(response, user, transport)

# Users routes (get/update user info)
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

router = auth_router
