"""Direct coverage for fact-check stats + exceptions."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agents.fact_checking.exceptions import (
    ClaimExtractionError,
    FactCheckError,
    SourceVerificationError,
)
from app.agents.fact_checking.fact_check_agent import FactCheckAgent
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod, SourceType
from app.services.fact_check_stats import get_fact_check_stats


def test_exception_hierarchy() -> None:
    assert issubclass(SourceVerificationError, FactCheckError)
    assert issubclass(ClaimExtractionError, FactCheckError)
    with pytest.raises(FactCheckError):
        raise ClaimExtractionError("x")


async def test_get_fact_check_stats_direct(session_factory) -> None:
    async with session_factory() as s:
        src = ContentSource(
            source_name="Docs", source_type=SourceType.DOCUMENTATION,
            source_url="https://ex.com", priority=1, credibility_score=0.9,
            freshness_score=0.8, relevance_score=0.9,
            preferred_collection_method=CollectionMethod.DOCUMENTATION,
            category="Agentic AI Engineering",
        )
        s.add(src)
        await s.flush()
        s.add(CollectedArticle(
            source_id=src.id, title="Agent orchestration framework launch",
            url="https://ex.com/story",
            raw_content="The agent achieves 95% accuracy on SWE-bench. OpenAI launches a framework.",
            summary="x", status=ArticleStatus.PROCESSED, is_selected=True,
            published_date=datetime.now(timezone.utc), source_category="Agentic AI Engineering",
        ))
        await s.commit()

    await FactCheckAgent(session_factory).run()

    async with session_factory() as s:
        stats = await get_fact_check_stats(s)
    assert stats.citations_created >= 1
    assert stats.claims_extracted >= 1
    assert stats.average_confidence_score > 0
    assert isinstance(stats.top_verified_sources, dict)
