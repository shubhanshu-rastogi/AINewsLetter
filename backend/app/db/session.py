"""Async SQLAlchemy engine, session factory, and FastAPI session dependency."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("db")


def _engine_kwargs() -> dict:
    kwargs: dict = {
        "echo": settings.DB_ECHO,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_recycle": 1800,
        "future": True,
    }
    # Per-statement timeout (PostgreSQL/asyncpg only) to bound runaway queries.
    if settings.DATABASE_URL.startswith("postgresql"):
        kwargs["connect_args"] = {
            "server_settings": {"statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS)}
        }
    return kwargs


# Single application-wide async engine. Creating the engine does NOT open a
# connection, so importing this module is safe even when the database is down.
engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs())


# Slow-query logging: warn when a statement exceeds DB_SLOW_QUERY_MS.
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    conn.info.setdefault("_query_start", []).append(time.perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    start_stack = conn.info.get("_query_start")
    if not start_stack:
        return
    elapsed_ms = (time.perf_counter() - start_stack.pop()) * 1000
    if elapsed_ms > settings.DB_SLOW_QUERY_MS:
        logger.warning("slow_query", duration_ms=round(elapsed_ms, 1), statement=statement[:200])

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a transactional database session.

    Commits on success, rolls back on exception, and always closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_database() -> bool:
    """Return ``True`` if a trivial query succeeds against the database."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_engine() -> None:
    """Dispose the engine and close all pooled connections (shutdown hook)."""
    await engine.dispose()
