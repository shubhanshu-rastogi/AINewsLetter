"""Pytest fixtures.

- ``client``: FastAPI TestClient for HTTP tests (no DB required).
- ``engine`` / ``session``: a fresh in-memory SQLite database per test, with
  foreign-key enforcement enabled so cascade behavior can be exercised.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Disable the background scheduler during tests (started in the app lifespan).
settings.ENABLE_SCHEDULER = False
# Keep fact-checking offline by default (no real URL HEAD requests).
settings.FACT_CHECK_VERIFY_URLS = False

from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db_session:
        yield db_session


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def workflow_service(session_factory):
    from langgraph.checkpoint.memory import MemorySaver

    from app.workflows.graph import build_newsletter_graph
    from app.workflows.service import WorkflowService

    return WorkflowService(build_newsletter_graph(checkpointer=MemorySaver()), session_factory)
