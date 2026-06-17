"""Model creation + default-value tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, SourceType, UserRole
from app.models.user import User


async def test_create_user_defaults(session: AsyncSession) -> None:
    user = User(email="a@b.com", name="A")
    session.add(user)
    await session.flush()

    assert user.id is not None
    assert user.role == UserRole.VIEWER  # default
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_create_source_and_article(session: AsyncSession) -> None:
    source = ContentSource(
        source_name="Example",
        source_type=SourceType.RSS,
        source_url="https://example.com",
        rss_url="https://example.com/feed",
    )
    session.add(source)
    await session.flush()

    article = CollectedArticle(
        source_id=source.id,
        title="Hello",
        url="https://example.com/post-1",
    )
    session.add(article)
    await session.flush()

    assert article.id is not None
    assert article.status == ArticleStatus.NEW  # default
    assert source.is_active is True
