"""Runtime context for workflow execution.

Nodes need a database session factory, but LangGraph nodes receive only the
state. We provide the factory via a ``ContextVar`` (set by the workflow service
around each invocation) so it is not stored in the checkpointer config. Falls
back to the application's default ``AsyncSessionLocal``.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AsyncSession]

_session_factory: ContextVar[SessionFactory | None] = ContextVar(
    "workflow_session_factory", default=None
)


def set_session_factory(factory: SessionFactory) -> Token:
    return _session_factory.set(factory)


def reset_session_factory(token: Token) -> None:
    _session_factory.reset(token)


def get_session_factory() -> SessionFactory:
    factory = _session_factory.get()
    if factory is not None:
        return factory
    from app.db.session import AsyncSessionLocal

    return AsyncSessionLocal
