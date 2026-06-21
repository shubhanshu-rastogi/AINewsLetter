"""Tests for the runtime settings + auth API (UI-managed config)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.core import crypto
from app.core.config import settings
from app.db.base import Base
from app.main import app


@pytest.fixture
def settings_client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'settings_api.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    async def _override_session():
        async with sf() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_crypto_round_trip() -> None:
    token = crypto.encrypt("super-secret-key")
    assert token != "super-secret-key"
    assert crypto.is_encrypted(token)
    assert crypto.decrypt(token) == "super-secret-key"
    # Plain (non-prefixed) values pass through unchanged.
    assert crypto.decrypt("plain") == "plain"


def test_settings_get_and_update(settings_client: TestClient) -> None:
    resp = settings_client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert any(f["key"] == "ANTHROPIC_API_KEY" and f["type"] == "secret" for f in body["fields"])
    # Secrets are never returned in plaintext.
    assert body["values"]["ANTHROPIC_API_KEY"] in ("", "__SET__")

    upd = settings_client.put(
        "/api/settings",
        json={"LLM_MODEL": "claude-test-model", "ANTHROPIC_API_KEY": "sk-test-123", "ENABLE_LLM_WRITER": True},
    )
    assert upd.status_code == 200
    out = upd.json()
    assert "LLM_MODEL" in out["changed"]
    # Applied to the live settings object.
    assert settings.LLM_MODEL == "claude-test-model"
    assert settings.ANTHROPIC_API_KEY == "sk-test-123"
    assert settings.ENABLE_LLM_WRITER is True
    # Re-read masks the secret but reports it as set.
    after = settings_client.get("/api/settings").json()
    assert after["values"]["LLM_MODEL"] == "claude-test-model"
    assert after["secret_set"]["ANTHROPIC_API_KEY"] is True
    assert after["values"]["ANTHROPIC_API_KEY"] == "__SET__"

    # A blank secret does not overwrite the stored one.
    settings_client.put("/api/settings", json={"ANTHROPIC_API_KEY": ""})
    assert settings.ANTHROPIC_API_KEY == "sk-test-123"


def test_auth_config_and_login(client: TestClient) -> None:
    cfg = client.get("/api/auth/config")
    assert cfg.status_code == 200
    # No REVIEW_AUTH_TOKEN configured in tests -> auth not required.
    assert cfg.json()["auth_required"] is False

    login = client.post("/api/auth/login", json={"token": "anything"})
    assert login.status_code == 200
    assert login.json()["ok"] is True

    assert client.get("/api/auth/verify").status_code == 200
