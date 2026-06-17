"""Declarative base for all ORM models.

- ``AsyncAttrs`` enables ``await instance.awaitable_attrs.<rel>`` for safe lazy
  loading under asyncio.
- A naming convention is applied to ``MetaData`` so indexes/constraints get
  deterministic names (important for clean Alembic migrations).
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Shared declarative base. All models inherit from this class."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
