"""SourceCollectionAgent - orchestrates collection, normalization, dedup, save."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.source_collection import (
    deduplicator,
    documentation_collector,
    newsletter_collector,
    normalizer,
    research_collector,
    rss_collector,
    source_strategy,
    web_collector,
)
from app.agents.source_collection.exceptions import (
    CollectionError,
    UnsupportedCollectionMethodError,
)
from app.agents.source_collection.types import CollectionResult, RawArticle
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.content_source import ContentSource
from app.models.enums import ArticleStatus, CollectionMethod
from app.models.system_setting import SystemSetting

logger = get_logger("collection.agent")

LAST_RUN_SETTING_KEY = "collection.last_run_at"


class SourceCollectionAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory
        self._dispatch: dict[
            CollectionMethod, Callable[[ContentSource], Awaitable[list[RawArticle]]]
        ] = {
            CollectionMethod.RSS: self.collect_rss,
            CollectionMethod.WEB: self.collect_website,
            CollectionMethod.DOCUMENTATION: self.collect_documentation,
            CollectionMethod.RESEARCH: self.collect_research,
            CollectionMethod.NEWSLETTER: self.collect_newsletter_source,
        }

    # ----- per-method collectors (thin wrappers) ----- #
    async def collect_rss(self, source: ContentSource) -> list[RawArticle]:
        return await rss_collector.collect_rss(source)

    async def collect_website(self, source: ContentSource) -> list[RawArticle]:
        return await web_collector.collect_website(source)

    async def collect_documentation(self, source: ContentSource) -> list[RawArticle]:
        return await documentation_collector.collect_documentation(source)

    async def collect_research(self, source: ContentSource) -> list[RawArticle]:
        return await research_collector.collect_research(source)

    async def collect_newsletter_source(self, source: ContentSource) -> list[RawArticle]:
        return await newsletter_collector.collect_newsletter_source(source)

    # ----- helpers ----- #
    def normalize_article(
        self, raw: RawArticle, source: ContentSource, method: CollectionMethod
    ) -> dict[str, Any]:
        return normalizer.normalize_article(raw, source, method)

    async def deduplicate_article(
        self, session: AsyncSession, normalized: dict, batch_titles: set[str]
    ) -> tuple[bool, str | None]:
        return await deduplicator.find_duplicate(session, normalized, batch_titles)

    async def save_article(self, session: AsyncSession, normalized: dict) -> str:
        article = CollectedArticle(**normalized)
        session.add(article)
        await session.flush()
        return str(article.id)

    def update_workflow_state(
        self, state: dict[str, Any], article_ids: list[str]
    ) -> dict[str, Any]:
        existing = list(state.get("collected_article_ids") or [])
        return {"collected_article_ids": existing + article_ids}

    async def _run_collector(
        self, source: ContentSource, method: CollectionMethod
    ) -> list[RawArticle]:
        collector = self._dispatch.get(method)
        if collector is None:
            raise UnsupportedCollectionMethodError(f"No collector for method {method}")
        return await collector(source)

    async def _collect_with_fallback(
        self, source: ContentSource
    ) -> tuple[list[RawArticle], CollectionMethod]:
        preferred = CollectionMethod(source.preferred_collection_method)
        try:
            return await self._run_collector(source, preferred), preferred
        except CollectionError as exc:
            fallback = source.fallback_collection_method
            if not fallback:
                raise
            logger.warning(
                "collection_fallback",
                source=source.source_name,
                preferred=str(preferred),
                fallback=str(fallback),
                error=str(exc),
            )
            fb = CollectionMethod(fallback)
            return await self._run_collector(source, fb), fb

    # ----- core ----- #
    async def _collect_source_obj(
        self, session: AsyncSession, source: ContentSource, batch_titles: set[str]
    ) -> CollectionResult:
        result = CollectionResult(source_id=str(source.id), source_name=source.source_name)
        logger.info("source_started", source=source.source_name)
        try:
            raws, method = await self._collect_with_fallback(source)
        except CollectionError as exc:
            result.failed = True
            result.error = str(exc)
            logger.error("collection_failed", source=source.source_name, error=str(exc))
            return result

        result.collected = len(raws)
        for raw in raws:
            normalized = self.normalize_article(raw, source, method)
            is_dup, reason = await self.deduplicate_article(
                session, normalized, batch_titles
            )
            if is_dup and reason == "same_url":
                result.duplicates += 1
                logger.info("duplicates_skipped", source=source.source_name, reason=reason)
                continue
            if is_dup:
                normalized["status"] = ArticleStatus.DUPLICATE
                await self.save_article(session, normalized)
                result.duplicates += 1
                continue
            article_id = await self.save_article(session, normalized)
            result.new += 1
            result.article_ids.append(article_id)
            batch_titles.add(normalized["title"])

        await session.commit()
        logger.info(
            "source_completed",
            source=source.source_name,
            collected=result.collected,
            new=result.new,
            duplicates=result.duplicates,
        )
        return result

    async def collect_source(self, source_id: str | uuid.UUID) -> CollectionResult:
        """Collect a single source by id (opens its own session)."""
        async with self.session_factory() as session:
            source = await session.get(ContentSource, uuid.UUID(str(source_id)))
            if source is None:
                return CollectionResult(
                    source_id=str(source_id), source_name="<unknown>", failed=True,
                    error="source not found",
                )
            return await self._collect_source_obj(session, source, set())

    async def collect_all_sources(self) -> list[str]:
        """Collect every active source (priority order). Returns NEW article ids."""
        logger.info("collection_started")
        async with self.session_factory() as session:
            sources = (
                await session.execute(
                    select(ContentSource).where(ContentSource.is_active.is_(True))
                )
            ).scalars().all()
            ordered = source_strategy.order_sources(sources)

            batch_titles: set[str] = set()
            new_ids: list[str] = []
            for source in ordered:
                result = await self._collect_source_obj(session, source, batch_titles)
                new_ids.extend(result.article_ids)

            await self._record_last_run(session)
            await session.commit()

        logger.info("collection_completed", new_articles=len(new_ids))
        return new_ids

    async def _record_last_run(self, session: AsyncSession) -> None:
        now = datetime.now(timezone.utc).isoformat()
        setting = await session.scalar(
            select(SystemSetting).where(SystemSetting.key == LAST_RUN_SETTING_KEY)
        )
        if setting is None:
            session.add(SystemSetting(key=LAST_RUN_SETTING_KEY, value=now))
        else:
            setting.value = now
