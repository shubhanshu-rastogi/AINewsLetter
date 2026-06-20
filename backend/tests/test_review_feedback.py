"""Review + feedback agent tests (Notion, LLM, sub-agent regen mocked)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.agents.review_feedback import feedback_classifier, notion_review, regeneration_planner
from app.agents.review_feedback.approval_router import route_decision
from app.agents.review_feedback.feedback_agent import FeedbackAgent
from app.agents.review_feedback.review_agent import ReviewAgent
from app.core.config import settings
from app.models.enums import (
    FeedbackCategory,
    FeedbackSeverity,
    NewsletterStatus,
    ReviewState,
)
from app.models.feedback_item import FeedbackItem
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.regeneration_plan import RegenerationPlan
from app.models.review_notification import ReviewNotification
from app.models.review_package import ReviewPackage
from app.models.review_session import ReviewSession
from app.models.review_version import ReviewVersion

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1},
    "executive_summary": "Weekly briefing.",
    "top_stories": [
        {
            "headline": "Agents ship",
            "what_happened": "x",
            "citation": {"source_name": "OpenAI", "publication_date": "2026-06-18"},
        }
    ],
    "tools": [],
    "testing": {"title": "t", "insight": "i"},
    "research": {"paper": "r", "key_findings": "k"},
    "benchmark": {"title": "b", "what_improved": "w"},
    "trends": [],
    "final_takeaways": ["a"],
}


async def _seed_newsletter(session_factory, content=CONTENT) -> str:
    async with session_factory() as s:
        nl = Newsletter(title="AI & Quality Engineering Weekly", issue_number=1, status=NewsletterStatus.DRAFT)
        s.add(nl)
        await s.flush()
        s.add(NewsletterDraft(newsletter_id=nl.id, content=content, current_version=1))
        await s.commit()
        return str(nl.id)


# --- package + session --- #
async def test_review_package_creation(session_factory) -> None:
    nid = await _seed_newsletter(session_factory)
    package = await ReviewAgent(session_factory).build_package(nid)
    assert package["title"] == CONTENT["cover"]["title"]
    assert package["issue_number"] == 1
    assert package["newsletter_draft"]["executive_summary"]
    assert package["approval_options"] == ["APPROVED", "FEEDBACK_REQUIRED", "REJECTED"]
    assert "fact_check" in package and "citations" in package


async def test_review_session_creation(session_factory) -> None:
    nid = await _seed_newsletter(session_factory)
    result = await ReviewAgent(session_factory).start_review(nid)
    assert result["review_session_id"]

    async with session_factory() as s:
        rs = (await s.execute(select(ReviewSession))).scalar_one()
        assert rs.review_state == ReviewState.PENDING.value
        assert await s.scalar(select(func.count()).select_from(ReviewPackage)) == 1
        assert await s.scalar(select(func.count()).select_from(ReviewNotification)) == 1
        nl = await s.get(Newsletter, uuid.UUID(nid))
        assert nl.status == NewsletterStatus.REVIEW


# --- Notion fallback + success --- #
async def test_notion_fallback_when_unconfigured() -> None:
    url = await notion_review.create_review_page({"title": "x"})
    assert url is None  # NOTION_API_KEY not set in tests


async def test_notion_success_mocked(monkeypatch) -> None:
    async def fake_create(payload):
        return "https://notion.so/review-123"

    monkeypatch.setattr(notion_review, "_notion_create_page", fake_create)
    monkeypatch.setattr(settings, "NOTION_API_KEY", "secret")
    monkeypatch.setattr(settings, "NOTION_REVIEW_DATABASE_ID", "db123")
    try:
        url = await notion_review.create_review_page(
            {"title": "x", "issue_number": 1, "newsletter_draft": {}, "fact_check": {}, "approval_options": []}
        )
    finally:
        monkeypatch.setattr(settings, "NOTION_API_KEY", None)
        monkeypatch.setattr(settings, "NOTION_REVIEW_DATABASE_ID", None)
    assert url == "https://notion.so/review-123"


# --- classification --- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Make the executive summary shorter and more direct.", FeedbackCategory.LENGTH_CHANGE),
        ("Adjust the tone to be more formal.", FeedbackCategory.TONE_CHANGE),
        ("Replace the research story with a better source.", FeedbackCategory.SOURCE_ISSUE),
        ("Visual slide 4 has too much text.", FeedbackCategory.VISUAL_CHANGE),
        ("This stat looks inaccurate / wrong.", FeedbackCategory.FACT_CHECK_ISSUE),
        ("Looks good to publish.", FeedbackCategory.APPROVAL_COMMENT),
    ],
)
def test_feedback_classification(text, expected) -> None:
    c = feedback_classifier.classify({"feedback_text": text})
    assert c.feedback_category == expected.value


def test_classification_severity_and_regen_flag() -> None:
    blocker = feedback_classifier.classify({"feedback_text": "Do not publish, this is fabricated."})
    assert blocker.severity == FeedbackSeverity.BLOCKER.value
    approval = feedback_classifier.classify({"feedback_text": "Looks good, ship it."})
    assert approval.regeneration_needed is False


# --- regeneration planning --- #
def test_regeneration_planning() -> None:
    items = [
        {
            "feedback_text": "Make this shorter.",
            "section_name": "Executive Summary",
            "feedback_category": "length_change",
            "artifact_type": "newsletter_section",
        },
        {
            "feedback_text": "Replace the research story.",
            "section_name": "Research Watch",
            "feedback_category": "source_issue",
            "artifact_type": "newsletter_section",
        },
        {
            "feedback_text": "Visual slide 4 has too much text.",
            "feedback_category": "visual_change",
            "artifact_type": "visual",
        },
        {
            "feedback_text": "Add more QA angle across the issue.",
            "feedback_category": "content_change",
            "artifact_type": "newsletter",
        },
    ]
    plan = regeneration_planner.build_plan(items)
    types = {(a["type"], a.get("section"), a.get("slide_number")) for a in plan["actions"]}
    assert ("regenerate_section", "executive_summary", None) in types
    assert ("replace_article_and_regenerate_section", "research", None) in types
    assert ("regenerate_carousel_slide", None, 4) in types
    assert ("regenerate_section", "testing", None) in types  # QA cross-cut


def test_plan_skips_approval_comments() -> None:
    plan = regeneration_planner.build_plan([{"feedback_text": "looks good", "feedback_category": "approval_comment"}])
    assert plan["actions"] == []


# --- approval routing --- #
def test_approval_routing() -> None:
    assert route_decision("APPROVED") == "publisher_node"
    assert route_decision("feedback_required") == "feedback_processor_node"
    assert route_decision("REJECTED") == "completion_node"
    assert route_decision(None) == "completion_node"


# --- targeted regeneration calls (sub-agents mocked) --- #
async def test_targeted_regeneration_calls(session_factory) -> None:
    agent = FeedbackAgent(session_factory)
    calls: list = []

    async def rec_section(nid, section, reason):
        calls.append(("section", section))

    async def rec_replace(nid, section, reason="x"):
        calls.append(("replace", section))

    async def rec_linkedin(nid):
        calls.append(("linkedin", None))

    async def rec_slide(nid, n):
        calls.append(("slide", n))

    async def rec_cover(nid):
        calls.append(("cover", None))

    agent.regenerate_newsletter_section = rec_section
    agent.replace_article_and_regenerate_section = rec_replace
    agent.regenerate_linkedin_post = rec_linkedin
    agent.regenerate_carousel_slide = rec_slide
    agent.regenerate_cover_image = rec_cover

    plan = {
        "actions": [
            {"type": "regenerate_section", "section": "research"},
            {"type": "replace_article_and_regenerate_section", "section": "research"},
            {"type": "regenerate_linkedin"},
            {"type": "regenerate_carousel_slide", "slide_number": 4},
            {"type": "regenerate_cover"},
        ]
    }
    changed = await agent.execute_plan("nid", plan)
    assert ("section", "research") in calls
    assert ("slide", 4) in calls
    assert ("cover", None) in calls
    assert len(changed) == 5


# --- feedback processing + version history --- #
async def test_process_feedback_creates_version_and_new_session(session_factory) -> None:
    nid = await _seed_newsletter(session_factory)
    start = await ReviewAgent(session_factory).start_review(nid)
    review_id = start["review_session_id"]

    agent = FeedbackAgent(session_factory)

    async def no_regen(newsletter_id, plan):
        return ["section:executive_summary"]

    agent.execute_plan = no_regen  # mock targeted regeneration

    result = await agent.process_feedback(
        review_id,
        items=[
            {
                "artifact_type": "newsletter_section",
                "section_name": "Executive Summary",
                "feedback_text": "Make this shorter.",
                "severity": "MEDIUM",
            }
        ],
        create_new_session=True,
    )
    assert result["new_review_session_id"]
    assert result["plan"]["actions"]

    async with session_factory() as s:
        old = await s.get(ReviewSession, uuid.UUID(review_id))
        assert old.review_state == ReviewState.SUPERSEDED.value
        assert await s.scalar(select(func.count()).select_from(FeedbackItem)) == 1
        assert await s.scalar(select(func.count()).select_from(RegenerationPlan)) == 1
        assert await s.scalar(select(func.count()).select_from(ReviewVersion)) >= 1
        fi = (await s.execute(select(FeedbackItem))).scalar_one()
        assert fi.feedback_category == "length_change"


# --- approval / rejection --- #
async def test_approval(session_factory) -> None:
    nid = await _seed_newsletter(session_factory)
    review_id = (await ReviewAgent(session_factory).start_review(nid))["review_session_id"]
    await ReviewAgent(session_factory).approve(review_id, "Looks good.", "editor")
    async with session_factory() as s:
        rs = await s.get(ReviewSession, uuid.UUID(review_id))
        nl = await s.get(Newsletter, uuid.UUID(nid))
    assert rs.review_state == ReviewState.APPROVED.value and rs.approved_at is not None
    assert nl.status == NewsletterStatus.APPROVED


async def test_rejection(session_factory) -> None:
    nid = await _seed_newsletter(session_factory)
    review_id = (await ReviewAgent(session_factory).start_review(nid))["review_session_id"]
    await ReviewAgent(session_factory).reject(review_id, "Do not publish.", "editor")
    async with session_factory() as s:
        rs = await s.get(ReviewSession, uuid.UUID(review_id))
        nl = await s.get(Newsletter, uuid.UUID(nid))
    assert rs.review_state == ReviewState.REJECTED.value and rs.rejected_at is not None
    assert nl.status == NewsletterStatus.ARCHIVED


async def test_missing_session_raises(session_factory) -> None:
    from app.agents.review_feedback.exceptions import ReviewSessionNotFoundError

    with pytest.raises(ReviewSessionNotFoundError):
        await ReviewAgent(session_factory).approve(str(uuid.uuid4()))
