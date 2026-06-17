"""Shared data types for collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class RawArticle:
    """A raw article emitted by a collector, before normalization."""

    title: str
    url: str
    author: str | None = None
    published_date: datetime | None = None
    raw_content: str | None = None
    summary: str | None = None
    categories: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CollectionResult:
    """Outcome of collecting a single source."""

    source_id: str
    source_name: str
    collected: int = 0
    new: int = 0
    duplicates: int = 0
    failed: bool = False
    error: str | None = None
    article_ids: list[str] = field(default_factory=list)
