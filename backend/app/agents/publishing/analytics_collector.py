"""Analytics collection (extensible; stores placeholders when APIs unavailable)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.publication_analytics import PublicationAnalytics

logger = get_logger("publishing.analytics")


async def collect_analytics(
    session: AsyncSession,
    *,
    newsletter_id: uuid.UUID,
    channel: str,
    publication_record_id: uuid.UUID | None,
    subscriber_count: int = 0,
) -> PublicationAnalytics:
    """Collect (or placeholder) analytics for a channel publication.

    Real metrics require channel APIs + a settling period; until then we store
    zeroed placeholders flagged with ``is_placeholder=True`` so they can be
    backfilled later.
    """
    placeholder = not settings.ENABLE_REAL_PUBLISHING
    record = PublicationAnalytics(
        newsletter_id=newsletter_id,
        publication_record_id=publication_record_id,
        channel=channel,
        publication_date=datetime.now(timezone.utc),
        open_count=0,
        click_count=0,
        impressions=0,
        engagement=0.0,
        subscriber_count=subscriber_count,
        growth_metrics={"net_new_subscribers": 0, "note": "placeholder" if placeholder else "pending"},
        is_placeholder=placeholder,
    )
    session.add(record)
    logger.info("analytics_collected", channel=channel, placeholder=placeholder)
    return record
