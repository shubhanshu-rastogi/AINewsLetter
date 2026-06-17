"""Relationship + cascade-delete tests."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import SourceType
from app.models.newsletter import Newsletter
from app.models.newsletter_section import NewsletterSection


async def test_newsletter_sections_relationship_and_cascade(
    session: AsyncSession,
) -> None:
    newsletter = Newsletter(title="Issue 1", issue_number=1)
    newsletter.sections = [
        NewsletterSection(section_name="AI News", section_order=0),
        NewsletterSection(section_name="AI Tools", section_order=1),
    ]
    session.add(newsletter)
    await session.flush()

    assert len(newsletter.sections) == 2

    # Cascade delete: removing the newsletter removes its sections.
    await session.delete(newsletter)
    await session.flush()

    remaining = await session.scalar(
        select(func.count()).select_from(NewsletterSection)
    )
    assert remaining == 0


async def test_source_articles_cascade(session: AsyncSession) -> None:
    source = ContentSource(
        source_name="S", source_type=SourceType.BLOG, source_url="https://s.dev"
    )
    source.articles = [
        CollectedArticle(title="t1", url="https://s.dev/1"),
        CollectedArticle(title="t2", url="https://s.dev/2"),
    ]
    session.add(source)
    await session.flush()

    await session.delete(source)
    await session.flush()

    remaining = await session.scalar(select(func.count()).select_from(CollectedArticle))
    assert remaining == 0
