"""Workflow API endpoint test (status endpoint)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.main import app
from app.workflows.service import WorkflowService, get_workflow_service


def test_workflow_endpoints(tmp_path) -> None:
    # File-based SQLite (NullPool) so connections work across the TestClient loop.
    url = f"sqlite+aiosqlite:///{tmp_path / 'wf_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    from langgraph.checkpoint.memory import MemorySaver

    from app.workflows.graph import build_newsletter_graph

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    service = WorkflowService(build_newsletter_graph(checkpointer=MemorySaver()), session_factory)
    app.dependency_overrides[get_workflow_service] = lambda: service

    try:
        with TestClient(app) as client:
            start = client.post("/api/workflows/newsletter/start")
            assert start.status_code == 202
            body = start.json()
            wf_id = body["workflow_run_id"]
            assert body["paused"] is True

            status = client.get(f"/api/workflows/{wf_id}/status")
            assert status.status_code == 200
            sbody = status.json()
            assert sbody["current_step"] == "human_review_node"
            assert sbody["paused"] is True

            state = client.get(f"/api/workflows/{wf_id}/state")
            assert state.status_code == 200
            assert state.json()["state"]["workflow_run_id"] == wf_id

            missing = client.get("/api/workflows/does-not-exist/status")
            assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
