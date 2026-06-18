"""Shared types for publishing."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import PublishState


@dataclass(slots=True)
class PublishResult:
    success: bool
    channel: str
    status: PublishState
    external_id: str | None = None
    error: str | None = None
    error_type: str | None = None
    metadata: dict = field(default_factory=dict)
