"""Production-readiness tests: config, secrets, health, metrics, redis, security."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.core.config import ConfigurationError, Settings, get_settings
from app.core.redis_client import InMemoryRedis, get_redis, reset_redis
from app.core.secrets import mask_secret, mask_text


# --- configuration --- #
def test_config_development_is_valid() -> None:
    s = Settings(APP_ENV="local")
    assert s.environment == "development"
    assert s.validate_for_environment() == []


def test_config_production_requires_secrets() -> None:
    s = Settings(APP_ENV="production", SECRET_KEY=None, POSTGRES_PASSWORD="postgres", CORS_ORIGINS="*")
    missing = s.validate_for_environment()
    assert any("SECRET_KEY" in m for m in missing)
    assert any("CORS_ORIGINS" in m for m in missing)
    assert any("POSTGRES_PASSWORD" in m for m in missing)


def test_config_production_valid_when_complete() -> None:
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="x" * 32,
        POSTGRES_PASSWORD="strong-pass",
        CORS_ORIGINS="https://app.example.com",
        ENABLE_REAL_PUBLISHING=False,
    )
    assert s.validate_for_environment() == []


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_configuration_error_is_runtime_error() -> None:
    assert issubclass(ConfigurationError, RuntimeError)


def test_database_url_override() -> None:
    s = Settings(DATABASE_URL_OVERRIDE="postgresql+asyncpg://u:p@h:5432/db")
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@h:5432/db"


# --- secrets / masking --- #
def test_mask_secret() -> None:
    assert mask_secret("supersecretkey", show=4) == "**********tkey"
    assert mask_secret("ab", show=4) == "**"
    assert mask_secret(None) == ""


def test_mask_text_redacts_tokens() -> None:
    assert "sk-1234567890abcdef" not in mask_text("key=sk-1234567890abcdef")
    masked_url = mask_text("postgresql://user:secretpw@host/db")
    assert "secretpw" not in masked_url
    assert "***" in mask_text("Authorization: Bearer abcdef123456")


# --- health endpoints --- #
def test_health_and_live(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    live = client.get("/health/live")
    assert live.status_code == 200 and live.json()["status"] == "ok"


def test_readiness_reports_dependencies(client: TestClient) -> None:
    # No database in the TestClient -> not ready (503), but structured.
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    names = {d["name"] for d in resp.json()["dependencies"]}
    assert {"database", "redis", "scheduler", "disk"} <= names


# --- metrics --- #
def test_metrics_endpoint(client: TestClient) -> None:
    client.get("/health")  # generate a request metric
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "ainl_request_count" in resp.text


# --- security headers --- #
def test_security_headers_present(client: TestClient) -> None:
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in headers


# --- redis fallback --- #
async def test_redis_in_memory_fallback() -> None:
    await reset_redis()
    redis = await get_redis()
    assert isinstance(redis, InMemoryRedis)  # ENABLE_REDIS off in tests
    assert await redis.set("k", "v", ex=60) is True
    assert await redis.get("k") == "v"
    assert await redis.incr("counter") == 1
    assert await redis.incr("counter") == 2
    assert await redis.setnx("k", "other") is False
    assert await redis.setnx("new", "1") is True
    assert await redis.delete("k") == 1
    assert await redis.get("k") is None
    assert await redis.ping() is True
    await reset_redis()


async def test_redis_expiry() -> None:
    redis = InMemoryRedis()
    await redis.set("temp", "v", ex=0)
    import time as _t

    _t.sleep(0.01)
    assert await redis.get("temp") is None


# --- rate limiting --- #
def test_rate_limiting_returns_429(monkeypatch) -> None:
    from app.api.deps import get_session
    from app.core import config as config_module
    from app.main import app

    monkeypatch.setattr(config_module.settings, "ENABLE_RATE_LIMIT", True)
    monkeypatch.setattr(config_module.settings, "RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(config_module.settings, "RATE_LIMIT_BURST", 0)
    asyncio.run(reset_redis())

    async def _fake_session():
        class _Stub:
            async def execute(self, *a, **k):
                class _R:
                    def scalars(self_inner):
                        class _S:
                            def all(self_more):
                                return []

                        return _S()

                return _R()

        yield _Stub()

    app.dependency_overrides[get_session] = _fake_session
    try:
        with TestClient(app) as c:
            statuses = [c.get("/api/publications").status_code for _ in range(4)]
    finally:
        app.dependency_overrides.clear()
        asyncio.run(reset_redis())
    assert 429 in statuses
    assert statuses.count(200) <= 2


# --- idempotency --- #
def test_idempotency_replays_response(monkeypatch, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import app.api.subscribers as sub_module
    from app.api.deps import get_session
    from app.core import config as config_module
    from app.db.base import Base
    from app.main import app

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'idem.db'}", poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    monkeypatch.setattr(sub_module, "AsyncSessionLocal", sf)
    monkeypatch.setattr(config_module.settings, "ENABLE_IDEMPOTENCY", True)
    asyncio.run(reset_redis())

    async def _override_session():
        async with sf() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as c:
            headers = {"Idempotency-Key": "abc-123"}
            first = c.post("/api/subscribers", json={"email": "a@b.com", "name": "A"}, headers=headers)
            second = c.post("/api/subscribers", json={"email": "a@b.com", "name": "A"}, headers=headers)
    finally:
        app.dependency_overrides.clear()
        asyncio.run(reset_redis())
        asyncio.run(engine.dispose())

    assert first.status_code == 201
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert second.json()["email"] == "a@b.com"
