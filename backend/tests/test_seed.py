"""Seed execution + idempotency tests."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import CATEGORIES, DEFAULT_SETTINGS, seed_all
from app.models.article_category import ArticleCategory
from app.models.enums import UserRole
from app.models.system_setting import SystemSetting
from app.models.user import User


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    first = await seed_all(session)
    assert first["categories"] == len(CATEGORIES)
    assert first["admin_user"] == 1
    assert first["system_settings"] == len(DEFAULT_SETTINGS)

    # Second run creates nothing new.
    second = await seed_all(session)
    assert second == {"categories": 0, "admin_user": 0, "system_settings": 0}

    cat_count = await session.scalar(select(func.count()).select_from(ArticleCategory))
    assert cat_count == len(CATEGORIES)

    setting_count = await session.scalar(select(func.count()).select_from(SystemSetting))
    assert setting_count == len(DEFAULT_SETTINGS)

    admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN))
    assert admin is not None
