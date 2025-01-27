from sqlalchemy.orm import Session
from fastapi import Depends
from .models import UserTable

# FASTAPI Users imports
from fastapi_users import FastAPIUsers
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
    CookieTransport
)
from fastapi_users import schemas
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session
from starlette.config import Config

# User Schemas
class UserRead(schemas.BaseUser[int]):
    first_name: str | None = None
    last_name: str | None = None

class UserCreate(schemas.BaseUserCreate):
    first_name: str | None = None
    last_name: str | None = None

class UserUpdate(schemas.BaseUserUpdate):
    first_name: str | None = None
    last_name: str | None = None

# Setup the user DB
async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, UserTable)

# Auth backend (JWT)
config = Config(".env")
JWT_SECRET = config("JWT_SECRET", default="CHANGE_ME_PLEASE")

# You can choose either bearer or cookie transport
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
cookie_transport = CookieTransport(cookie_max_age=3600)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=JWT_SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield user_db

fastapi_users = FastAPIUsers[UserTable, int](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)

# Routers
auth_router = APIRouter()

# Include the authentication routes
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
)

# Include the registration routes
auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"]
)

# Include the users routes
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"]
)

router = auth_router