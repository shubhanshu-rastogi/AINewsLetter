"""Reusable SQLAlchemy column types."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=Enum)


def str_enum(enum_cls: type[E], name: str, length: int = 50) -> SAEnum:
    """Build a portable, non-native enum column.

    Stored as ``VARCHAR`` with a ``CHECK`` constraint (``native_enum=False``)
    so it works identically on PostgreSQL and SQLite, and persists the enum's
    *value* (not its member name) via ``values_callable``.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        validate_strings=True,
    )
