from fastapi import APIRouter, Depends, Response
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

# User Schemas
class UserRead(schemas.BaseUser[int]):
    first_name: str | None = None
    last_name: str | None = None
    first_login_at: datetime | None = None
    email: str
    class Config:
        orm_mode = True

class UserCreate(schemas.BaseUserCreate):
    first_name: str | None = None
    last_name: str | None = None

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
    cookie_secure=False, # Must be false for HTTP
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_domain="localhost",
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

# Routes
auth_router = APIRouter()

# Authentication routes (login/logout) - Use cookie endpoints
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),  # Use the cookie backend
    prefix="/auth/cookie",                      # /auth/cookie/login, /auth/cookie/logout
    tags=["auth"],
)

# Registration routes
auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# Users routes (get/update user info)
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

router = auth_router
