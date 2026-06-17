"""Idempotent seed data.

Running these functions repeatedly is safe: each insert is guarded by an
existence check on a unique key, so re-seeding never creates duplicates.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.article_category import ArticleCategory
from app.models.enums import UserRole
from app.models.system_setting import SystemSetting
from app.models.user import User

logger = get_logger("seed")

CATEGORIES: list[tuple[str, str]] = [
    ("AI News", "Latest news across the artificial intelligence landscape."),
    ("AI Tools", "New and notable AI tools, libraries, and products."),
    ("QA Testing", "Quality assurance, testing strategy, and automation."),
    ("Software Engineering", "Engineering practices, architecture, and craft."),
    ("Enterprise AI", "AI adoption and platforms in the enterprise."),
    ("Career Development", "Career growth for engineers and technologists."),
]

DEFAULT_ADMIN_EMAIL = "admin@ainewsletter.local"
DEFAULT_ADMIN_NAME = "Platform Admin"

DEFAULT_SETTINGS: dict[str, str] = {
    "newsletter.cadence": "weekly",
    "newsletter.timezone": "UTC",
    "newsletter.min_items": "8",
    "llm.default_provider": "anthropic",
}


async def seed_categories(session: AsyncSession) -> int:
    created = 0
    for name, description in CATEGORIES:
        exists = await session.scalar(
            select(ArticleCategory).where(ArticleCategory.name == name)
        )
        if exists is None:
            session.add(ArticleCategory(name=name, description=description))
            created += 1
    return created


async def seed_admin_user(session: AsyncSession) -> int:
    exists = await session.scalar(
        select(User).where(User.email == DEFAULT_ADMIN_EMAIL)
    )
    if exists is not None:
        return 0
    session.add(
        User(email=DEFAULT_ADMIN_EMAIL, name=DEFAULT_ADMIN_NAME, role=UserRole.ADMIN)
    )
    return 1


async def seed_system_settings(session: AsyncSession) -> int:
    created = 0
    for key, value in DEFAULT_SETTINGS.items():
        exists = await session.scalar(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        if exists is None:
            session.add(SystemSetting(key=key, value=value))
            created += 1
    return created


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Seed all reference data within the given session (caller commits)."""
    result = {
        "categories": await seed_categories(session),
        "admin_user": await seed_admin_user(session),
        "system_settings": await seed_system_settings(session),
    }
    await session.flush()
    return result


async def run_seed() -> dict[str, int]:
    """Open a session, seed, and commit. Used by the CLI seed script."""
    async with AsyncSessionLocal() as session:
        result = await seed_all(session)
        await session.commit()
    logger.info("seed_completed", **result)
    return result
