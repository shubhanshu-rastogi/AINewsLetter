"""Alembic migration environment.

Resolves the database URL in this order:
  1. ``-x db_url=...`` passed on the command line
  2. ``ALEMBIC_DATABASE_URL`` environment variable
  3. application settings (``settings.DATABASE_URL``)

Supports both async drivers (``asyncpg`` / ``aiosqlite``) and sync drivers
(e.g. plain ``sqlite://`` used in tests/CI).
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from app.core.config import settings
from app.db.base import Base  # noqa: F401 - registers all models on metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    return (
        x_args.get("db_url")
        or os.environ.get("ALEMBIC_DATABASE_URL")
        or settings.DATABASE_URL
    )


def _is_async(url: str) -> bool:
    return "+asyncpg" in url or "+aiosqlite" in url


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations(url: str) -> None:
    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    url = get_url()
    if _is_async(url):
        asyncio.run(run_async_migrations(url))
    else:
        connectable = create_engine(url, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            do_run_migrations(connection)
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
