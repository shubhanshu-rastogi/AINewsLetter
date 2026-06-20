"""FeedbackAgent - capture, classify, plan, and execute targeted regeneration."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.newsletter_writer.writer_agent import NewsletterWriterAgent
from app.agents.review_feedback import feedback_classifier, regeneration_planner, version_tracker
from app.agents.review_feedback.exceptions import ReviewSessionNotFoundError
from app.agents.review_feedback.review_agent import ReviewAgent
from app.agents.visual_generation.visual_agent import VisualGenerationAgent
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle
from app.models.enums import (
    FeedbackType,
    NewsletterSection,
    ResolutionStatus,
    ReviewState,
    ReviewStatus,
)
from app.models.feedback_item import FeedbackItem
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter_draft import NewsletterDraft
from app.models.regeneration_plan import RegenerationPlan
from app.models.review_session import ReviewSession

logger = get_logger("feedback")

# content key -> NewsletterSection for article replacement.
_SECTION_ENUM = {
    "research": NewsletterSection.RESEARCH_WATCH,
    "benchmark": NewsletterSection.CODING_AGENT_BENCHMARK,
    "testing": NewsletterSection.AI_TESTING_QUALITY,
    "enterprise": NewsletterSection.ENTERPRISE_AI_ADOPTION,
    "tools": NewsletterSection.AI_TOOLS_WATCH,
    "trends": NewsletterSection.WEEKLY_TREND_SIGNALS,
}


class FeedbackAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory
        self.writer = NewsletterWriterAgent(session_factory)
        self.visual = VisualGenerationAgent(session_factory)
        self.review_agent = ReviewAgent(session_factory)

    # ------------------------------------------------------------------ #
    # Classification + planning
    # ------------------------------------------------------------------ #
    def classify_feedback(self, items: Sequence[dict]) -> list[dict]:
        classified: list[dict] = []
        for raw in items:
            c = feedback_classifier.classify(raw)
            classified.append({**raw, **asdict(c)})
        return classified

    def plan_regeneration(self, classified: Sequence[dict]) -> dict:
        return regeneration_planner.build_plan(list(classified))

    # ------------------------------------------------------------------ #
    # Targeted regeneration primitives
    # ------------------------------------------------------------------ #
    async def regenerate_newsletter_section(self, newsletter_id: str, section: str, reason: str) -> None:
        await self.writer.regenerate_section(newsletter_id, section, reason=reason, changed_by="feedback-agent")

    async def regenerate_linkedin_post(self, newsletter_id: str) -> None:
        async with self.session_factory() as session:
            nid = uuid.UUID(newsletter_id)
            draft = await session.scalar(select(NewsletterDraft).where(NewsletterDraft.newsletter_id == nid))
            post_text = self.writer.generate_linkedin_post(draft.content if draft else {})
            li = await session.scalar(select(LinkedInPost).where(LinkedInPost.newsletter_id == nid))
            if li is not None:
                li.body = post_text
                li.char_count = len(post_text)
            await session.commit()

    async def regenerate_carousel_slide(self, newsletter_id: str, slide_number: int) -> None:
        async with self.session_factory() as session:
            visual = await session.scalar(
                select(GeneratedVisual).where(
                    GeneratedVisual.newsletter_id == uuid.UUID(newsletter_id),
                    GeneratedVisual.visual_kind == "carousel_slide",
                    GeneratedVisual.slide_number == slide_number,
                )
            )
            visual_id = str(visual.id) if visual else None
        if visual_id:
            await self.visual.version_visual(visual_id, reason="feedback")

    async def regenerate_cover_image(self, newsletter_id: str) -> None:
        async with self.session_factory() as session:
            visual = await session.scalar(
                select(GeneratedVisual).where(
                    GeneratedVisual.newsletter_id == uuid.UUID(newsletter_id),
                    GeneratedVisual.visual_kind == "cover",
                )
            )
            visual_id = str(visual.id) if visual else None
        if visual_id:
            await self.visual.version_visual(visual_id, reason="feedback")
        else:
            await self.visual.generate_cover_only(newsletter_id)

    async def replace_article_and_regenerate_section(
        self, newsletter_id: str, section: str, reason: str = "replace article"
    ) -> None:
        ns = _SECTION_ENUM.get(section)
        if ns is not None:
            async with self.session_factory() as session:
                rows = (
                    (
                        await session.execute(
                            select(CollectedArticle)
                            .where(
                                CollectedArticle.newsletter_section == ns,
                                CollectedArticle.verification_status.is_not(None),
                            )
                            .order_by(CollectedArticle.overall_confidence_score.desc())
                        )
                    )
                    .scalars()
                    .all()
                )
                current = [a for a in rows if a.is_selected]
                alternatives = [a for a in rows if not a.is_selected]
                if current and alternatives:
                    current[0].is_selected = False
                    alternatives[0].is_selected = True
                    await session.commit()
        await self.regenerate_newsletter_section(newsletter_id, section, reason)

    async def execute_plan(self, newsletter_id: str, plan: dict) -> list[str]:
        changed: list[str] = []
        for action in plan.get("actions", []):
            kind = action["type"]
            reason = action.get("reason", "feedback")
            if kind == "regenerate_section":
                await self.regenerate_newsletter_section(newsletter_id, action["section"], reason)
                changed.append(f"section:{action['section']}")
            elif kind == "replace_article_and_regenerate_section":
                await self.replace_article_and_regenerate_section(newsletter_id, action["section"], reason)
                changed.append(f"replace:{action['section']}")
            elif kind == "regenerate_linkedin":
                await self.regenerate_linkedin_post(newsletter_id)
                changed.append("linkedin")
            elif kind == "regenerate_carousel_slide":
                await self.regenerate_carousel_slide(newsletter_id, action["slide_number"])
                changed.append(f"slide:{action['slide_number']}")
            elif kind == "regenerate_cover":
                await self.regenerate_cover_image(newsletter_id)
                changed.append("cover")
        logger.info("targeted_regeneration_completed", changed=len(changed))
        return changed

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #
    async def process_feedback(
        self,
        review_session_id: str,
        items: Sequence[dict] | None = None,
        *,
        create_new_session: bool = True,
    ) -> dict[str, Any]:
        logger.info("feedback_received", review_session_id=review_session_id)
        async with self.session_factory() as session:
            rs = await session.get(ReviewSession, uuid.UUID(str(review_session_id)))
            if rs is None:
                raise ReviewSessionNotFoundError(review_session_id)
            newsletter_id = str(rs.newsletter_id)

            if items:
                classified = self.classify_feedback(items)
                for c in classified:
                    session.add(
                        FeedbackItem(
                            review_session_id=rs.id,
                            feedback_text=c.get("feedback_text"),
                            feedback_type=FeedbackType.GENERAL,
                            resolution_status=ResolutionStatus.OPEN,
                            artifact_type=c.get("artifact_type"),
                            section_name=c.get("section_name"),
                            feedback_category=c.get("feedback_category"),
                            severity=c.get("severity"),
                            action_required=c.get("action_required"),
                            regeneration_needed=c.get("regeneration_needed"),
                        )
                    )
            else:
                classified = [
                    {
                        "feedback_text": fi.feedback_text,
                        "artifact_type": fi.artifact_type,
                        "section_name": fi.section_name,
                        "feedback_category": fi.feedback_category
                        or feedback_classifier.classify(
                            {
                                "feedback_text": fi.feedback_text,
                                "artifact_type": fi.artifact_type,
                                "section_name": fi.section_name,
                            }
                        ).feedback_category,
                    }
                    for fi in rs.feedback_items
                ]

            plan = self.plan_regeneration(classified)
            session.add(RegenerationPlan(review_session_id=rs.id, plan=plan, executed=False))
            await version_tracker.record_version(
                session,
                rs.newsletter_id,
                review_session_id=rs.id,
                feedback_summary=[c.get("feedback_text") for c in classified],
                regeneration_plan=plan,
                reviewer_decision="feedback_required",
            )
            rs.review_state = ReviewState.SUPERSEDED.value
            rs.review_status = ReviewStatus.CHANGES_REQUESTED
            for fi in rs.feedback_items:
                fi.resolution_status = ResolutionStatus.RESOLVED
            await session.commit()

        # Execute regeneration (sub-agents manage their own sessions/commits).
        changed = await self.execute_plan(newsletter_id, plan)

        new_session = None
        if create_new_session:
            new_session = await self.review_agent.start_review(newsletter_id)
        logger.info("new_version_created", newsletter_id=newsletter_id, changed=len(changed))

        return {
            "review_session_id": review_session_id,
            "newsletter_id": newsletter_id,
            "plan": plan,
            "changed_sections": changed,
            "new_review_session_id": new_session["review_session_id"] if new_session else None,
        }
