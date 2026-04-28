import os
import sys
import asyncio
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure project root is on path
if os.getenv("ALEMBIC_ADD_REPO_ROOT", "0") == "1":
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

# Load env early
load_dotenv(".env")

DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL not set in environment or .env!")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from api.db_base import Base as ApiBase  # noqa: E402

from auth_service.db_base import Base as AuthBase  # noqa: E402

import api.models  # noqa: F401, E402
import auth_service.models  # noqa: F401, E402

config.set_main_option("sqlalchemy.url", DB_URL)

target_metadata = [ApiBase.metadata, AuthBase.metadata]


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(DB_URL, pool_pre_ping=True, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
