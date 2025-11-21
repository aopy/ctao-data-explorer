import logging

import redis.asyncio as redis
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=False for production

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


# The dependency function
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# Redis Setup
REDIS_URL = settings.REDIS_URL
redis_pool = None


async def get_redis_pool():
    global redis_pool
    if redis_pool is None:
        # print(f"Connecting to Redis at {REDIS_URL}")
        redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    return redis_pool


async def get_redis_client() -> redis.Redis:
    pool = await get_redis_pool()
    return redis.Redis(connection_pool=pool)


# Encryption Setup for Refresh Tokens
ENCRYPTION_KEY_STR = settings.REFRESH_TOKEN_ENCRYPTION_KEY
if not ENCRYPTION_KEY_STR:
    logger.warning(
        "REFRESH_TOKEN_ENCRYPTION_KEY is not set. Refresh token storage will be insecure."
    )
    fernet_cipher = None
else:
    try:
        fernet_cipher = Fernet(ENCRYPTION_KEY_STR.encode())
    except Exception as e:
        logger.error(
            "Invalid REFRESH_TOKEN_ENCRYPTION_KEY: %s. Refresh token storage will fail.",
            e,
        )
        fernet_cipher = None


def encrypt_token(token: str) -> str | None:
    if fernet_cipher and token:
        return fernet_cipher.encrypt(token.encode()).decode()
    return None


def decrypt_token(encrypted_token: str) -> str | None:
    if fernet_cipher and encrypted_token:
        try:
            return fernet_cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.exception("Failed to decrypt refresh token: %s", e)
            return None
    return None
