"""Extra production coverage: size limit, health helpers, recovery edges, tracing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.secrets import EnvSecretProvider, get_secret, set_secret_provider
from app.core.tracing import setup_tracing
from app.services import health_service
from app.services.workflow_recovery import WorkflowRecoveryService


# --- request size limit --- #
def test_request_size_limit_returns_413(monkeypatch) -> None:
    from app.core import config as config_module
    from app.main import app

    monkeypatch.setattr(config_module.settings, "MAX_REQUEST_BYTES", 5)
    with TestClient(app) as c:
        resp = c.post("/api/subscribers", json={"email": "a@b.com", "name": "long enough body"})
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "request_too_large"


# --- health helpers --- #
def test_get_health() -> None:
    h = health_service.get_health()
    assert h.status == "ok" and h.environment


def test_check_disk_and_scheduler() -> None:
    assert health_service._check_disk().name == "disk"  # noqa: SLF001
    sched = health_service._check_scheduler()  # noqa: SLF001
    assert sched.name == "scheduler" and sched.healthy is True  # scheduler disabled in tests


async def test_check_redis_enabled_but_unavailable(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "ENABLE_REDIS", True)
    dep = await health_service._check_redis()  # noqa: SLF001
    # Falls back to in-memory which is not "real" redis -> reported unhealthy.
    assert dep.name == "redis" and dep.healthy is False


async def test_readiness_structure() -> None:
    result = await health_service.get_readiness()
    assert result.ready is False  # no real DB
    assert len(result.dependencies) == 4


# --- recovery edges --- #
def test_ensure_scheduler_disabled(session_factory) -> None:
    assert WorkflowRecoveryService(session_factory).ensure_scheduler() is False


async def test_recover_failed_publications_abandons(session_factory) -> None:
    from sqlalchemy import select

    from app.models.enums import NewsletterStatus, PublicationChannel, PublicationStatus, PublishState
    from app.models.newsletter import Newsletter
    from app.models.publication_record import PublicationRecord
    from app.models.retry_queue import RetryQueueEntry

    async with session_factory() as s:
        # Unapproved newsletter -> retry will fail -> entry abandoned at max attempts.
        nl = Newsletter(title="N", issue_number=1, status=NewsletterStatus.DRAFT)
        s.add(nl)
        await s.flush()
        rec = PublicationRecord(
            newsletter_id=nl.id,
            channel=PublicationChannel.BEEHIIV,
            publication_status=PublicationStatus.FAILED,
            publish_state=PublishState.RETRYING.value,
            retry_count=2,
        )
        s.add(rec)
        await s.flush()
        s.add(
            RetryQueueEntry(
                publication_record_id=rec.id,
                newsletter_id=nl.id,
                channel="beehiiv",
                attempt=2,
                max_retries=3,
                status="pending",
            )
        )
        await s.commit()

    result = await WorkflowRecoveryService(session_factory).recover_failed_publications()
    assert result["abandoned"] == 1
    async with session_factory() as s:
        entry = (await s.execute(select(RetryQueueEntry))).scalar_one()
    assert entry.status == "abandoned"


# --- tracing --- #
def test_tracing_disabled_returns_false() -> None:
    assert setup_tracing(object()) is False  # ENABLE_TRACING off in tests


def test_tracing_enabled_without_otel_returns_false(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "ENABLE_TRACING", True)
    # OpenTelemetry not installed -> import error caught -> False.
    assert setup_tracing(object()) is False


# --- secrets provider --- #
def test_secret_provider(monkeypatch) -> None:
    monkeypatch.setenv("MY_TEST_SECRET", "value123")
    assert get_secret("MY_TEST_SECRET") == "value123"
    assert get_secret("MISSING", "fallback") == "fallback"

    class _Custom(EnvSecretProvider):
        def get(self, name, default=None):
            return "custom"

    set_secret_provider(_Custom())
    try:
        assert get_secret("anything") == "custom"
    finally:
        set_secret_provider(EnvSecretProvider())
