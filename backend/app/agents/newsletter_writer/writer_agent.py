"""NewsletterWriterAgent - generates, versions, and regenerates newsletters."""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.newsletter_writer import linkedin_generator, llm, section_generator
from app.agents.newsletter_writer.brand import BrandVoice, load_brand
from app.agents.newsletter_writer.exceptions import UnknownSectionError
from app.core.config import settings
from app.core.logging import get_logger
from app.models.carousel_outline import CarouselOutline
from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection as NS
from app.models.enums import NewsletterStatus, VerificationStatus
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.newsletter_section import NewsletterSection
from app.models.newsletter_version import NewsletterVersion
from app.models.regeneration_history import RegenerationHistory

logger = get_logger("writer")

MAX_STORIES = 5
MAX_TOOLS = 3
MAX_TRENDS = 3
REGENERATABLE = {
    "executive_summary", "top_stories", "tools", "testing", "enterprise",
    "research", "benchmark", "trends", "final_takeaways",
}
_PUBLISHABLE = {VerificationStatus.VERIFIED.value, VerificationStatus.REVIEW_REQUIRED.value}


class NewsletterWriterAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory
        self.brand: BrandVoice = load_brand()

    # ------------------------------------------------------------------ #
    # Article loading / grouping
    # ------------------------------------------------------------------ #
    async def _load_articles(
        self, session: AsyncSession, article_ids: Sequence[str] | None
    ) -> list[CollectedArticle]:
        stmt = select(CollectedArticle).where(
            CollectedArticle.verification_status.in_(_PUBLISHABLE)
        )
        if article_ids is not None:
            ids = [uuid.UUID(str(a)) for a in article_ids]
            if not ids:
                return []
            stmt = stmt.where(CollectedArticle.id.in_(ids))
        else:
            stmt = stmt.where(CollectedArticle.is_selected.is_(True))
        articles = list((await session.execute(stmt)).scalars().all())
        articles.sort(key=lambda a: a.overall_confidence_score or 0.0, reverse=True)
        return articles

    @staticmethod
    def _in_section(articles: Sequence[CollectedArticle], section: NS) -> list[CollectedArticle]:
        return [a for a in articles if a.newsletter_section == section]

    # ------------------------------------------------------------------ #
    # Section generators (per spec)
    # ------------------------------------------------------------------ #
    def generate_top_stories(self, articles: Sequence[CollectedArticle]) -> list[dict]:
        return [section_generator.story(a) for a in articles[:MAX_STORIES]]

    def generate_tools_section(self, articles: Sequence[CollectedArticle]) -> list[dict]:
        return [section_generator.tool(a) for a in self._in_section(articles, NS.AI_TOOLS_WATCH)[:MAX_TOOLS]]

    def generate_testing_section(self, articles: Sequence[CollectedArticle]) -> dict | None:
        pool = self._in_section(articles, NS.AI_TESTING_QUALITY) or self._in_section(
            articles, NS.AI_EVALUATION_QA_GATES
        )
        return section_generator.testing_insight(pool[0]) if pool else None

    def generate_enterprise_section(self, articles: Sequence[CollectedArticle]) -> dict | None:
        pool = self._in_section(articles, NS.ENTERPRISE_AI_ADOPTION)
        return section_generator.enterprise_insight(pool[0]) if pool else None

    def generate_research_section(self, articles: Sequence[CollectedArticle]) -> dict | None:
        pool = self._in_section(articles, NS.RESEARCH_WATCH)
        return section_generator.research_insight(pool[0]) if pool else None

    def generate_benchmark_section(self, articles: Sequence[CollectedArticle]) -> dict | None:
        pool = self._in_section(articles, NS.CODING_AGENT_BENCHMARK)
        return section_generator.benchmark_insight(pool[0]) if pool else None

    def generate_trends_section(self, articles: Sequence[CollectedArticle]) -> list[dict]:
        return [section_generator.trend(a) for a in self._in_section(articles, NS.WEEKLY_TREND_SIGNALS)[:MAX_TRENDS]]

    def generate_executive_summary(self, stories: Sequence[dict]) -> str:
        return section_generator.executive_summary(stories, self.brand)

    def generate_final_takeaways(self, content: dict) -> list[str]:
        return section_generator.final_takeaways(content)

    # ------------------------------------------------------------------ #
    # LinkedIn / social
    # ------------------------------------------------------------------ #
    def generate_linkedin_post(self, content: dict) -> str:
        return linkedin_generator.announcement_post(content, self.brand)

    def generate_carousel_outline(self, content: dict) -> list[dict]:
        return linkedin_generator.carousel_outline(content, self.brand)

    def generate_email_subject_lines(self, content: dict) -> list[str]:
        return linkedin_generator.email_subject_lines(content, self.brand)

    # ------------------------------------------------------------------ #
    # Content assembly
    # ------------------------------------------------------------------ #
    def _build_content(
        self, articles: Sequence[CollectedArticle], issue_number: int | None
    ) -> dict:
        top_stories = self.generate_top_stories(articles)
        content: dict[str, Any] = {
            "cover": {
                "title": self.brand.name,
                "tagline": self.brand.tagline,
                "issue_number": issue_number,
                "publication_date": datetime.now(timezone.utc).date().isoformat(),
            },
            "top_stories": top_stories,
            "tools": self.generate_tools_section(articles),
            "testing": self.generate_testing_section(articles),
            "enterprise": self.generate_enterprise_section(articles),
            "research": self.generate_research_section(articles),
            "benchmark": self.generate_benchmark_section(articles),
            "trends": self.generate_trends_section(articles),
        }
        content["executive_summary"] = self.generate_executive_summary(top_stories)
        content["final_takeaways"] = self.generate_final_takeaways(content)

        words = self._word_count(content)
        content["cover"]["word_count"] = words
        content["cover"]["estimated_reading_time_minutes"] = max(1, math.ceil(words / 200))
        return content

    @staticmethod
    def _word_count(content: dict) -> int:
        def walk(obj) -> int:
            if isinstance(obj, str):
                return len(obj.split())
            if isinstance(obj, dict):
                return sum(walk(v) for v in obj.values())
            if isinstance(obj, list):
                return sum(walk(v) for v in obj)
            return 0

        # Exclude the cover meta from the body word count.
        return sum(walk(v) for k, v in content.items() if k != "cover")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def _resolve_newsletter(
        self, session: AsyncSession, newsletter_id: str | None
    ) -> Newsletter:
        if newsletter_id:
            nl = await session.get(Newsletter, uuid.UUID(str(newsletter_id)))
            if nl is not None:
                return nl
        max_issue = await session.scalar(select(func.max(Newsletter.issue_number)))
        nl = Newsletter(
            title=self.brand.name,
            issue_number=(max_issue or 0) + 1,
            status=NewsletterStatus.DRAFT,
        )
        session.add(nl)
        await session.flush()
        return nl

    async def _persist_sections(
        self, session: AsyncSession, newsletter_id: uuid.UUID, content: dict
    ) -> int:
        await session.execute(
            delete(NewsletterSection).where(NewsletterSection.newsletter_id == newsletter_id)
        )
        order = 0
        for key in ("executive_summary", "top_stories", "tools", "testing", "enterprise",
                    "research", "benchmark", "trends", "final_takeaways"):
            value = content.get(key)
            if not value:
                continue
            text = self._render_section(key, value)
            session.add(NewsletterSection(
                newsletter_id=newsletter_id, section_name=key, section_order=order,
                content=text, word_count=len(text.split()),
            ))
            order += 1
        return order

    @staticmethod
    def _render_section(key: str, value: Any) -> str:
        if isinstance(value, str):
            return value
        return str(value)

    async def save_draft(
        self,
        session: AsyncSession,
        newsletter: Newsletter,
        content: dict,
        *,
        version_number: int,
        created_by: str,
        reason: str | None,
        generation_time_ms: float | None = None,
        subjects: list[str] | None = None,
    ) -> NewsletterDraft:
        words = content["cover"].get("word_count", 0)
        reading_time = content["cover"].get("estimated_reading_time_minutes", 1)

        draft = await session.scalar(
            select(NewsletterDraft).where(NewsletterDraft.newsletter_id == newsletter.id)
        )
        if draft is None:
            draft = NewsletterDraft(newsletter_id=newsletter.id)
            session.add(draft)
        draft.title = content["cover"]["title"]
        draft.content = content
        draft.word_count = words
        draft.reading_time_minutes = reading_time
        draft.current_version = version_number
        if subjects is not None:
            draft.email_subjects = subjects
        if generation_time_ms is not None:
            draft.generation_time_ms = generation_time_ms

        session.add(NewsletterVersion(
            newsletter_id=newsletter.id, version_number=version_number,
            content=content, word_count=words, created_by=created_by, change_reason=reason,
        ))
        newsletter.summary = content.get("executive_summary")
        newsletter.version = version_number
        return draft

    # ------------------------------------------------------------------ #
    # Public orchestration
    # ------------------------------------------------------------------ #
    async def generate_newsletter(
        self,
        article_ids: Sequence[str] | None = None,
        newsletter_id: str | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        logger.info("newsletter_generation_started")
        start = time.perf_counter()
        async with self.session_factory() as session:
            newsletter = await self._resolve_newsletter(session, newsletter_id)
            articles = await self._load_articles(session, article_ids)
            content = self._build_content(articles, newsletter.issue_number)

            if settings.ENABLE_LLM_WRITER and content.get("executive_summary"):
                content["executive_summary"] = await llm.polish_text(
                    content["executive_summary"], self.brand
                )

            linkedin_post = self.generate_linkedin_post(content)
            carousel = self.generate_carousel_outline(content)
            subjects = self.generate_email_subject_lines(content)
            logger.info("linkedin_post_generated")
            logger.info("carousel_generated")

            gen_ms = round((time.perf_counter() - start) * 1000, 2)
            sections = await self._persist_sections(session, newsletter.id, content)
            version_number = await self._next_version(session, newsletter.id)
            await self.save_draft(
                session, newsletter, content, version_number=version_number,
                created_by=created_by, reason="initial generation",
                generation_time_ms=gen_ms, subjects=subjects,
            )
            await self._replace_social(session, newsletter.id, linkedin_post, carousel)
            await session.commit()
            nl_id = str(newsletter.id)

        logger.info(
            "newsletter_generation_completed",
            newsletter_id=nl_id, sections=sections, words=content["cover"]["word_count"],
        )
        return {
            "newsletter_id": nl_id,
            "content": content,
            "linkedin_post": linkedin_post,
            "carousel": carousel,
            "email_subjects": subjects,
            "word_count": content["cover"]["word_count"],
            "reading_time_minutes": content["cover"]["estimated_reading_time_minutes"],
            "version": version_number,
            "sections_generated": sections,
            "generation_time_ms": gen_ms,
        }

    async def _next_version(self, session: AsyncSession, newsletter_id: uuid.UUID) -> int:
        current = await session.scalar(
            select(func.max(NewsletterVersion.version_number)).where(
                NewsletterVersion.newsletter_id == newsletter_id
            )
        )
        return (current or 0) + 1

    async def _replace_social(
        self, session: AsyncSession, newsletter_id: uuid.UUID, post: str, carousel: list[dict]
    ) -> None:
        await session.execute(delete(LinkedInPost).where(LinkedInPost.newsletter_id == newsletter_id))
        await session.execute(delete(CarouselOutline).where(CarouselOutline.newsletter_id == newsletter_id))
        session.add(LinkedInPost(
            newsletter_id=newsletter_id, variant="announcement", body=post,
            hashtags=["#AI", "#QualityEngineering", "#Testing", "#AgenticAI"],
            char_count=len(post),
        ))
        session.add(CarouselOutline(newsletter_id=newsletter_id, slides=carousel))

    async def regenerate_section(
        self, newsletter_id: str, section: str, *, reason: str, changed_by: str = "system"
    ) -> dict[str, Any]:
        if section not in REGENERATABLE:
            raise UnknownSectionError(f"Cannot regenerate unknown section '{section}'")
        logger.info("section_regenerated_started", section=section)

        async with self.session_factory() as session:
            nl = await session.get(Newsletter, uuid.UUID(str(newsletter_id)))
            draft = await session.scalar(
                select(NewsletterDraft).where(NewsletterDraft.newsletter_id == nl.id)
            )
            content = dict(draft.content or {})
            articles = await self._load_articles(session, None)

            content[section] = self._regenerate_one(section, articles, content)
            if section == "top_stories":  # dependent sections refresh
                content["executive_summary"] = self.generate_executive_summary(content["top_stories"])
            content["final_takeaways"] = self.generate_final_takeaways(content)

            words = self._word_count(content)
            content["cover"]["word_count"] = words
            content["cover"]["estimated_reading_time_minutes"] = max(1, math.ceil(words / 200))

            from_version = draft.current_version
            to_version = from_version + 1
            await self._persist_sections(session, nl.id, content)
            await self.save_draft(
                session, nl, content, version_number=to_version,
                created_by=changed_by, reason=reason,
            )
            session.add(RegenerationHistory(
                newsletter_id=nl.id, section_name=section,
                from_version=from_version, to_version=to_version,
                changed_by=changed_by, reason=reason,
            ))
            await session.commit()

        logger.info("section_regenerated", section=section, version=to_version)
        return {"newsletter_id": newsletter_id, "section": section,
                "version": to_version, "content": content[section]}

    def _regenerate_one(self, section: str, articles, content: dict):
        match section:
            case "top_stories":
                return self.generate_top_stories(articles)
            case "tools":
                return self.generate_tools_section(articles)
            case "testing":
                return self.generate_testing_section(articles)
            case "enterprise":
                return self.generate_enterprise_section(articles)
            case "research":
                return self.generate_research_section(articles)
            case "benchmark":
                return self.generate_benchmark_section(articles)
            case "trends":
                return self.generate_trends_section(articles)
            case "executive_summary":
                return self.generate_executive_summary(content.get("top_stories", []))
            case "final_takeaways":
                return self.generate_final_takeaways(content)
        raise UnknownSectionError(section)

    def update_workflow_state(self, content: dict, linkedin_post: str) -> dict[str, Any]:
        return {
            "newsletter_draft": content,
            "linkedin_draft": {"body": linkedin_post},
        }

    async def run(
        self, article_ids: Sequence[str] | None = None, newsletter_id: str | None = None
    ) -> dict[str, Any]:
        return await self.generate_newsletter(article_ids, newsletter_id)
