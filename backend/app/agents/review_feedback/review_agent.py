"""ReviewAgent - review sessions, packages, Notion pages, approval/rejection."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.review_feedback import notion_review, version_tracker
from app.agents.review_feedback.exceptions import ReviewSessionNotFoundError
from app.agents.review_feedback.review_package_builder import build_review_package
from app.core.logging import get_logger
from app.models.enums import NewsletterStatus, ReviewState, ReviewStatus
from app.models.newsletter import Newsletter
from app.models.review_notification import ReviewNotification
from app.models.review_package import ReviewPackage
from app.models.review_session import ReviewSession

logger = get_logger("review")

_ACTIVE_STATES = (ReviewState.PENDING.value, ReviewState.FEEDBACK_REQUIRED.value)
_LEGACY = {
    ReviewState.PENDING: ReviewStatus.PENDING,
    ReviewState.FEEDBACK_REQUIRED: ReviewStatus.CHANGES_REQUESTED,
    ReviewState.SUPERSEDED: ReviewStatus.CHANGES_REQUESTED,
    ReviewState.APPROVED: ReviewStatus.APPROVED,
    ReviewState.REJECTED: ReviewStatus.REJECTED,
}


def send_review_notification(payload: dict) -> dict:
    """Email notification placeholder - logs the payload (no email sent yet)."""
    logger.info(
        "review_notification_prepared", **{k: payload[k] for k in ("review_session_id", "subject") if k in payload}
    )
    return payload


class ReviewAgent:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    async def build_package(self, newsletter_id: str) -> dict:
        async with self.session_factory() as session:
            return await build_review_package(session, newsletter_id)

    async def start_review(
        self, newsletter_id: str, content: dict | None = None, reviewer: str | None = None
    ) -> dict[str, Any]:
        nid = uuid.UUID(str(newsletter_id))
        async with self.session_factory() as session:
            # Supersede any currently active review sessions for this newsletter.
            await session.execute(
                update(ReviewSession)
                .where(
                    ReviewSession.newsletter_id == nid,
                    ReviewSession.review_state.in_(_ACTIVE_STATES),
                )
                .values(review_state=ReviewState.SUPERSEDED.value, review_status=ReviewStatus.CHANGES_REQUESTED)
            )

            version = await version_tracker.next_version_number(session, nid)
            review = ReviewSession(
                newsletter_id=nid,
                reviewer=reviewer,
                review_status=ReviewStatus.PENDING,
                review_state=ReviewState.PENDING.value,
                version_number=version,
            )
            session.add(review)
            await session.flush()

            package = await build_review_package(session, newsletter_id)
            session.add(ReviewPackage(review_session_id=review.id, newsletter_id=nid, package=package))

            notion_url = await notion_review.create_review_page(package)
            review.notion_page_url = notion_url

            payload = {
                "review_session_id": str(review.id),
                "subject": f"Review needed: {package.get('title')} (Issue {package.get('issue_number')})",
                "summary": package.get("executive_summary")
                or package.get("newsletter_draft", {}).get("executive_summary"),
                "notion_page_url": notion_url,
            }
            session.add(
                ReviewNotification(review_session_id=review.id, channel="email", status="prepared", payload=payload)
            )
            send_review_notification(payload)

            newsletter = await session.get(Newsletter, nid)
            if newsletter is not None:
                newsletter.status = NewsletterStatus.REVIEW

            await session.commit()
            result = {
                "review_session_id": str(review.id),
                "newsletter_id": str(nid),
                "version_number": version,
                "notion_page_url": notion_url,
                "notion_fallback": notion_url is None,
                "package": package,
            }
        logger.info("review_session_created", review_session_id=result["review_session_id"])
        return result

    async def get_session(self, review_session_id: str) -> ReviewSession:
        async with self.session_factory() as session:
            rs = await session.get(ReviewSession, uuid.UUID(str(review_session_id)))
            if rs is None:
                raise ReviewSessionNotFoundError(review_session_id)
            return rs

    async def get_package(self, review_session_id: str) -> dict:
        async with self.session_factory() as session:
            pkg = await session.scalar(
                select(ReviewPackage).where(ReviewPackage.review_session_id == uuid.UUID(str(review_session_id)))
            )
            return pkg.package if pkg else {}

    async def list_for_newsletter(self, newsletter_id: str) -> Sequence[ReviewSession]:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(ReviewSession)
                .where(ReviewSession.newsletter_id == uuid.UUID(str(newsletter_id)))
                .order_by(ReviewSession.created_at.desc())
            )
            return rows.scalars().all()

    async def _decide(
        self,
        review_session_id: str,
        *,
        state: ReviewState,
        comments: str | None,
        reviewer: str | None,
        newsletter_status: NewsletterStatus,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            rs = await session.get(ReviewSession, uuid.UUID(str(review_session_id)))
            if rs is None:
                raise ReviewSessionNotFoundError(review_session_id)
            rs.review_state = state.value
            rs.review_status = _LEGACY[state]
            rs.comments = comments
            rs.reviewer = reviewer or rs.reviewer
            if state == ReviewState.APPROVED:
                rs.approved_at = now
            elif state == ReviewState.REJECTED:
                rs.rejected_at = now

            newsletter = await session.get(Newsletter, rs.newsletter_id)
            if newsletter is not None:
                newsletter.status = newsletter_status
            await version_tracker.record_version(
                session,
                rs.newsletter_id,
                review_session_id=rs.id,
                reviewer_decision=state.value,
            )
            await session.commit()
            result = {"review_session_id": review_session_id, "review_state": state.value}
        logger.info(f"review_{state.value}", review_session_id=review_session_id)
        return result

    async def approve(
        self, review_session_id: str, comments: str | None = None, reviewer: str | None = None
    ) -> dict[str, Any]:
        return await self._decide(
            review_session_id,
            state=ReviewState.APPROVED,
            comments=comments,
            reviewer=reviewer,
            newsletter_status=NewsletterStatus.APPROVED,
        )

    async def reject(
        self, review_session_id: str, comments: str | None = None, reviewer: str | None = None
    ) -> dict[str, Any]:
        return await self._decide(
            review_session_id,
            state=ReviewState.REJECTED,
            comments=comments,
            reviewer=reviewer,
            newsletter_status=NewsletterStatus.ARCHIVED,
        )
