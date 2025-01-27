from starlette.config import Config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

config = Config(".env")

DATABASE_URL = config("DATABASE_URL", default="postgresql+asyncpg://user:pass@127.0.0.1:5432/mydb")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# The dependency function
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

Base = declarative_base()
