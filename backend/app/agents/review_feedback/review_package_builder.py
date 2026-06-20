"""Builds the complete, review-ready package for a newsletter."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.visual_generation.asset_storage import get_storage
from app.core.logging import get_logger
from app.models.carousel_outline import CarouselOutline
from app.models.collected_article import CollectedArticle
from app.models.enums import ReviewState
from app.models.generated_visual import GeneratedVisual
from app.models.linkedin_post import LinkedInPost
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.regeneration_history import RegenerationHistory

logger = get_logger("review.package")

APPROVAL_OPTIONS = ["APPROVED", "FEEDBACK_REQUIRED", "REJECTED"]


def _citations_from_content(content: dict) -> list[dict]:
    citations: list[dict] = []
    for story in content.get("top_stories", []):
        if story.get("citation"):
            citations.append(story["citation"])
    for tool in content.get("tools", []):
        if tool.get("citation"):
            citations.append(tool["citation"])
    for key in ("research", "benchmark"):
        item = content.get(key)
        if isinstance(item, dict) and item.get("citation"):
            citations.append(item["citation"])
    return citations


async def build_review_package(session: AsyncSession, newsletter_id: str) -> dict:
    nid = uuid.UUID(str(newsletter_id))
    newsletter = await session.get(Newsletter, nid)
    if newsletter is None:
        return {}

    draft = await session.scalar(select(NewsletterDraft).where(NewsletterDraft.newsletter_id == nid))
    content = (draft.content if draft else {}) or {}

    linkedin = await session.scalar(select(LinkedInPost).where(LinkedInPost.newsletter_id == nid))
    carousel = await session.scalar(select(CarouselOutline).where(CarouselOutline.newsletter_id == nid))
    visuals = (
        (await session.execute(select(GeneratedVisual).where(GeneratedVisual.newsletter_id == nid))).scalars().all()
    )
    selected = (
        (
            await session.execute(
                select(CollectedArticle).where(
                    CollectedArticle.is_selected.is_(True),
                    CollectedArticle.verification_status.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    history = (
        (await session.execute(select(RegenerationHistory).where(RegenerationHistory.newsletter_id == nid)))
        .scalars()
        .all()
    )

    storage = get_storage()
    confidences = [a.overall_confidence_score for a in selected if a.overall_confidence_score]
    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    package = {
        "newsletter_id": str(nid),
        "title": newsletter.title,
        "issue_number": newsletter.issue_number,
        "publication_date": content.get("cover", {}).get("publication_date"),
        "newsletter_draft": content,
        "linkedin_post": {"body": linkedin.body, "hashtags": linkedin.hashtags} if linkedin else None,
        "carousel_outline": carousel.slides if carousel else None,
        "visuals": [
            {
                "id": str(v.id),
                "visual_kind": v.visual_kind,
                "preview_url": storage.url_for(v.file_path) if v.file_path else None,
                "width": v.width,
                "height": v.height,
            }
            for v in visuals
        ],
        "citations": _citations_from_content(content),
        "fact_check": {
            "average_confidence_score": avg_conf,
            "results": [
                {
                    "article_id": str(a.id),
                    "title": a.title,
                    "verification_status": a.verification_status,
                    "confidence": a.overall_confidence_score,
                }
                for a in selected
            ],
        },
        "evidence_summary": [
            {"article_id": str(a.id), "status": a.verification_status, "confidence_score": a.overall_confidence_score}
            for a in selected
        ],
        "regeneration_history": [
            {
                "section": h.section_name,
                "from_version": h.from_version,
                "to_version": h.to_version,
                "reason": h.reason,
                "changed_by": h.changed_by,
            }
            for h in history
        ],
        "approval_options": APPROVAL_OPTIONS,
        "review_states": [s.value for s in ReviewState],
    }
    logger.info("review_package_created", newsletter_id=str(nid), visuals=len(visuals))
    return package
