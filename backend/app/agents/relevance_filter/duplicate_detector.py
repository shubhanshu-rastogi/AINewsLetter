"""Duplicate detection + canonical story grouping.

Groups articles that are the same story (same URL, same content hash, or highly
similar title) and elects a canonical representative (highest overall score).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models.collected_article import CollectedArticle

TITLE_SIMILARITY_THRESHOLD = 0.85


@dataclass(slots=True)
class StoryGroup:
    canonical: CollectedArticle
    members: list[CollectedArticle] = field(default_factory=list)


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= TITLE_SIMILARITY_THRESHOLD


def _same_story(a: CollectedArticle, b: CollectedArticle) -> bool:
    if a.url and a.url == b.url:
        return True
    if a.content_hash and a.content_hash == b.content_hash:
        return True
    return _similar(a.title or "", b.title or "")


def _score(article: CollectedArticle) -> tuple[float, float]:
    return (article.overall_relevance_score or 0.0, article.credibility_score or 0.0)


def group_stories(articles: Sequence[CollectedArticle]) -> list[StoryGroup]:
    """Cluster articles into story groups (greedy, by same-story predicate)."""
    groups: list[StoryGroup] = []
    for article in articles:
        placed = False
        for group in groups:
            if _same_story(group.canonical, article):
                group.members.append(article)
                if _score(article) > _score(group.canonical):
                    group.canonical = article
                placed = True
                break
        if not placed:
            groups.append(StoryGroup(canonical=article, members=[article]))
    return groups


def assign_canonical_ids(groups: Sequence[StoryGroup]) -> int:
    """Set ``canonical_story_id`` on every member. Returns duplicates merged."""
    merged = 0
    for group in groups:
        story_id = group.canonical.id or uuid.uuid4()
        for member in group.members:
            member.canonical_story_id = story_id
            if member.id != group.canonical.id:
                merged += 1
    return merged
