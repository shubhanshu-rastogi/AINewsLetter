"""PublisherAgent - validates, publishes (multi-channel), tracks, and retries."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.publishing import (
    analytics_collector,
    beehiiv_publisher,
    email_preparer,
    linkedin_publisher,
    publication_tracker,
)
from app.agents.publishing.exceptions import (
    PublicationNotApprovedError,
    PublishError,
    RetryablePublishError,
    ValidationFailedError,
)
from app.agents.publishing.retry_manager import run_with_retry
from app.agents.publishing.subscriber_manager import SubscriberManager
from app.agents.publishing.types import PublishResult
from app.agents.review_feedback.review_package_builder import build_review_package
from app.core.logging import get_logger
from app.models.enums import (
    NewsletterStatus,
    PublicationChannel,
    PublicationStatus,
    PublishState,
    ReviewState,
)
from app.models.newsletter import Newsletter
from app.models.publication_analytics import PublicationAnalytics  # noqa: F401 (registry)
from app.models.publication_failure import PublicationFailure
from app.models.retry_queue import RetryQueueEntry
from app.models.review_session import ReviewSession

logger = get_logger("publishing")

_DEFAULT_CHANNELS = [PublicationChannel.BEEHIIV, PublicationChannel.LINKEDIN, PublicationChannel.EMAIL]


class PublisherAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory
        self.subscribers = SubscriberManager(session_factory)

    # ------------------------------------------------------------------ #
    # Validation (never publish unapproved)
    # ------------------------------------------------------------------ #
    async def validate_publication_package(self, newsletter_id: str) -> dict[str, Any]:
        logger.info("publication_validation_started", newsletter_id=newsletter_id)
        nid = uuid.UUID(str(newsletter_id))
        async with self.session_factory() as session:
            newsletter = await session.get(Newsletter, nid)
            if newsletter is None:
                raise ValidationFailedError("Newsletter not found.")
            if newsletter.status != NewsletterStatus.APPROVED:
                raise PublicationNotApprovedError(f"Newsletter status is {newsletter.status}, not APPROVED.")
            approved_review = await session.scalar(
                select(ReviewSession).where(
                    ReviewSession.newsletter_id == nid,
                    ReviewSession.review_state == ReviewState.APPROVED.value,
                )
            )
            if approved_review is None:
                raise PublicationNotApprovedError("No approved review session found.")

            package = await build_review_package(session, newsletter_id)

        if not package.get("newsletter_draft"):
            raise ValidationFailedError("Newsletter draft is missing.")

        warnings = []
        for key in ("linkedin_post", "carousel_outline", "visuals", "citations"):
            if not package.get(key):
                warnings.append(f"missing:{key}")
        cover = next((v for v in package.get("visuals", []) if v.get("visual_kind") == "cover"), None)
        package["cover_image_url"] = cover["preview_url"] if cover else None

        return {"approved": True, "valid": True, "warnings": warnings, "package": package}

    # ------------------------------------------------------------------ #
    # Channel publishing
    # ------------------------------------------------------------------ #
    async def _publish_channel(self, channel: PublicationChannel, package: dict) -> PublishResult:
        if channel == PublicationChannel.EMAIL:
            email = email_preparer.prepare_email(package, package.get("cover_image_url"))
            return PublishResult(
                success=True,
                channel="email",
                status=PublishState.PUBLISHED,
                metadata={"prepared": True, "delivered": False, "subject": email["subject"]},
            )
        if channel == PublicationChannel.BEEHIIV:
            return await run_with_retry(lambda: beehiiv_publisher.publish(package))
        # LINKEDIN: announcement post (required) + carousel (best effort)
        result = await run_with_retry(lambda: linkedin_publisher.publish_post(package))
        try:
            carousel = await run_with_retry(lambda: linkedin_publisher.publish_carousel(package))
            result.metadata["carousel_external_id"] = carousel.external_id
        except PublishError as exc:
            result.metadata["carousel_error"] = str(exc)
        return result

    async def publish_newsletter(self, newsletter_id: str, channels: Sequence[str] | None = None) -> dict[str, Any]:
        validation = await self.validate_publication_package(newsletter_id)
        package = validation["package"]
        chans = [PublicationChannel(c.lower()) for c in channels] if channels else _DEFAULT_CHANNELS
        subscriber_count = await self.subscribers.active_count()

        results: dict[str, Any] = {}
        for channel in chans:
            results[channel.value] = await self._publish_one(newsletter_id, channel, package, subscriber_count)

        published = [c for c, r in results.items() if r["status"] == "published"]
        failed = [c for c, r in results.items() if r["status"] != "published"]
        overall = "published" if not failed else ("partial" if published else "failed")
        logger.info("publication_completed", newsletter_id=newsletter_id, overall=overall)
        return {
            "newsletter_id": newsletter_id,
            "channels": results,
            "overall": overall,
            "publish_status": overall,
        }

    async def _publish_one(
        self, newsletter_id: str, channel: PublicationChannel, package: dict, subscriber_count: int
    ) -> dict[str, Any]:
        try:
            result = await self._publish_channel(channel, package)
            await self.record_publication(newsletter_id, channel, result, subscriber_count)
            return {"status": "published", "external_id": result.external_id, "metadata": result.metadata}
        except PublishError as exc:
            retryable = isinstance(exc, RetryablePublishError)
            await self._record_failure(newsletter_id, channel, exc, retryable=retryable)
            logger.error("publication_failed", channel=channel.value, error=str(exc), retryable=retryable)
            return {
                "status": "retrying" if retryable else "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def record_publication(
        self,
        newsletter_id: str,
        channel: PublicationChannel,
        result: PublishResult,
        subscriber_count: int = 0,
    ) -> None:
        nid = uuid.UUID(str(newsletter_id))
        async with self.session_factory() as session:
            record = await publication_tracker.get_or_create_record(session, nid, channel)
            record.publication_status = PublicationStatus.PUBLISHED
            record.publish_state = PublishState.PUBLISHED.value
            record.publication_date = datetime.now(timezone.utc)
            record.external_publication_id = result.external_id
            record.error_message = None
            record.channel_metadata = result.metadata
            await session.flush()
            await analytics_collector.collect_analytics(
                session,
                newsletter_id=nid,
                channel=channel.value,
                publication_record_id=record.id,
                subscriber_count=subscriber_count,
            )
            await session.commit()

    async def _record_failure(
        self,
        newsletter_id: str,
        channel: PublicationChannel,
        exc: Exception,
        *,
        retryable: bool,
    ) -> None:
        nid = uuid.UUID(str(newsletter_id))
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            record = await publication_tracker.get_or_create_record(session, nid, channel)
            record.publication_status = PublicationStatus.FAILED
            record.publish_state = (PublishState.RETRYING if retryable else PublishState.FAILED).value
            record.error_message = str(exc)
            record.retry_count = (record.retry_count or 0) + 1
            record.last_retry_at = now
            await session.flush()

            session.add(
                PublicationFailure(
                    publication_record_id=record.id,
                    newsletter_id=nid,
                    channel=channel.value,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    occurred_at=now,
                )
            )
            if retryable:
                session.add(
                    RetryQueueEntry(
                        publication_record_id=record.id,
                        newsletter_id=nid,
                        channel=channel.value,
                        attempt=record.retry_count,
                        status="pending",
                        last_error=str(exc),
                    )
                )
                logger.info("retry_scheduled", channel=channel.value, attempt=record.retry_count)
            await session.commit()

    # ------------------------------------------------------------------ #
    # Public helpers (per-spec function names)
    # ------------------------------------------------------------------ #
    async def publish_linkedin_post(self, newsletter_id: str) -> dict[str, Any]:
        return await self.publish_newsletter(newsletter_id, [PublicationChannel.LINKEDIN.value])

    async def publish_carousel(self, newsletter_id: str) -> PublishResult:
        validation = await self.validate_publication_package(newsletter_id)
        return await run_with_retry(lambda: linkedin_publisher.publish_carousel(validation["package"]))

    async def prepare_email(self, newsletter_id: str) -> dict[str, Any]:
        validation = await self.validate_publication_package(newsletter_id)
        return email_preparer.prepare_email(validation["package"], validation["package"].get("cover_image_url"))

    async def collect_analytics(self, newsletter_id: str, channel: str) -> dict[str, Any]:
        nid = uuid.UUID(str(newsletter_id))
        async with self.session_factory() as session:
            record = await session.scalar(
                select(PublicationAnalytics).where(
                    PublicationAnalytics.newsletter_id == nid,
                    PublicationAnalytics.channel == channel,
                )
            )
            return {"channel": channel, "exists": record is not None}

    async def schedule_retry(self, publication_id: str) -> dict[str, Any]:
        return await self.retry_publication(publication_id)

    async def retry_publication(self, publication_id: str) -> dict[str, Any]:
        from app.models.publication_record import PublicationRecord

        async with self.session_factory() as session:
            record = await session.get(PublicationRecord, uuid.UUID(str(publication_id)))
            if record is None:
                raise ValidationFailedError("Publication record not found.")
            newsletter_id = str(record.newsletter_id)
            channel = record.channel
        result = await self.publish_newsletter(newsletter_id, [channel.value])
        return {
            "publication_id": publication_id,
            "channel": channel.value,
            "result": result["channels"].get(channel.value),
        }

    def update_workflow_state(self, overall: str) -> dict[str, Any]:
        return {"publish_status": overall}
