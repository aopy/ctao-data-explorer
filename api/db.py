from starlette.config import Config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import redis.asyncio as redis
from cryptography.fernet import Fernet
# import os
from typing import Optional


config = Config(".env")

DATABASE_URL = config("DATABASE_URL", default="postgresql+asyncpg://user:pass@127.0.0.1:5432/mydb")
engine = create_async_engine(DATABASE_URL, echo=True) # echo=False for production

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
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
redis_pool = None

async def get_redis_pool():
    global redis_pool
    if redis_pool is None:
        print(f"Connecting to Redis at {REDIS_URL}")
        redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    return redis_pool

async def get_redis_client() -> redis.Redis:
    pool = await get_redis_pool()
    return redis.Redis(connection_pool=pool)

# Encryption Setup for Refresh Tokens
ENCRYPTION_KEY_STR = config("REFRESH_TOKEN_ENCRYPTION_KEY", default="")
if not ENCRYPTION_KEY_STR:
    print("WARNING: REFRESH_TOKEN_ENCRYPTION_KEY is not set. Refresh token storage will be insecure.")
    fernet_cipher = None
else:
    try:
        fernet_cipher = Fernet(ENCRYPTION_KEY_STR.encode())
    except Exception as e:
        print(f"ERROR: Invalid REFRESH_TOKEN_ENCRYPTION_KEY: {e}. Refresh token storage will fail.")
        fernet_cipher = None

def encrypt_token(token: str) -> Optional[str]:
    if fernet_cipher and token:
        return fernet_cipher.encrypt(token.encode()).decode()
    return None

def decrypt_token(encrypted_token: str) -> Optional[str]:
    if fernet_cipher and encrypted_token:
        try:
            return fernet_cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            print(f"ERROR: Failed to decrypt token: {e}")
            return None
    return None
