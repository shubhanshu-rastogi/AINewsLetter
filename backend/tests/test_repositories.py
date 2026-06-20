"""Repository CRUD + pagination tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SourceType, UserRole
from app.repositories.source_repository import SourceRepository
from app.repositories.user_repository import UserRepository


async def test_user_repository_crud(session: AsyncSession) -> None:
    repo = UserRepository(session)

    user = await repo.create({"email": "u@example.com", "name": "U", "role": UserRole.EDITOR})
    assert user.id is not None

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == "u@example.com"

    by_email = await repo.get_by_email("u@example.com")
    assert by_email is not None and by_email.id == user.id

    updated = await repo.update(user, {"name": "Updated"})
    assert updated.name == "Updated"

    await repo.delete(user)
    assert await repo.get_by_id(user.id) is None


async def test_source_repository_pagination(session: AsyncSession) -> None:
    repo = SourceRepository(session)

    for i in range(7):
        await repo.create(
            {
                "source_name": f"src-{i}",
                "source_type": SourceType.RSS,
                "source_url": f"https://example.com/{i}",
                "is_active": i % 2 == 0,
            }
        )

    page1 = await repo.paginate(page=1, page_size=5)
    assert page1.total == 7
    assert len(page1.items) == 5
    assert page1.pages == 2

    page2 = await repo.paginate(page=2, page_size=5)
    assert len(page2.items) == 2

    active = await repo.list_active()
    assert len(active) == 4  # indices 0,2,4,6
