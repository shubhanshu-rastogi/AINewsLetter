"""Newsletter writer statistics."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.newsletter_draft import NewsletterDraft
from app.models.newsletter_section import NewsletterSection
from app.models.regeneration_history import RegenerationHistory
from app.schemas.writer import NewsletterStats


async def get_newsletter_stats(session: AsyncSession) -> NewsletterStats:
    generated = await session.scalar(select(func.count()).select_from(NewsletterDraft))
    avg_time = await session.scalar(select(func.avg(NewsletterDraft.generation_time_ms)))
    avg_words = await session.scalar(select(func.avg(NewsletterDraft.word_count)))
    sections = await session.scalar(select(func.count()).select_from(NewsletterSection))
    regenerations = await session.scalar(
        select(func.count()).select_from(RegenerationHistory)
    )
    top_rows = await session.execute(
        select(RegenerationHistory.section_name, func.count())
        .group_by(RegenerationHistory.section_name)
        .order_by(func.count().desc())
        .limit(10)
    )

    return NewsletterStats(
        newsletters_generated=int(generated or 0),
        average_generation_time_ms=round(float(avg_time), 2) if avg_time else 0.0,
        average_word_count=round(float(avg_words), 2) if avg_words else 0.0,
        sections_generated=int(sections or 0),
        regenerations_performed=int(regenerations or 0),
        top_sections_regenerated={k: c for k, c in top_rows},
    )
