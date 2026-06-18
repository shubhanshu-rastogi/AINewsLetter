"""Turns classified feedback into a targeted regeneration plan.

Only the impacted artifacts are scheduled for regeneration - never the whole
newsletter unless feedback demands it.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.models.enums import ArtifactType, FeedbackCategory

logger = get_logger("feedback.planner")

# Human section name -> newsletter content key.
_SECTION_ALIASES: dict[str, str] = {
    "executive summary": "executive_summary",
    "summary": "executive_summary",
    "top stories": "top_stories",
    "big picture": "top_stories",
    "tools": "tools",
    "ai tools": "tools",
    "testing": "testing",
    "quality": "testing",
    "qa": "testing",
    "enterprise": "enterprise",
    "research": "research",
    "research watch": "research",
    "benchmark": "benchmark",
    "coding agent": "benchmark",
    "trends": "trends",
    "trend signals": "trends",
    "final takeaways": "final_takeaways",
    "takeaways": "final_takeaways",
}
_SLIDE_RE = re.compile(r"slide\s*#?\s*(\d{1,2})", re.IGNORECASE)


def resolve_section(section_name: str | None, text: str) -> str | None:
    haystack = f"{section_name or ''} {text}".lower()
    for alias, key in _SECTION_ALIASES.items():
        if alias in haystack:
            return key
    return None


def _slide_number(text: str) -> int | None:
    match = _SLIDE_RE.search(text or "")
    return int(match.group(1)) if match else None


def _action_for(item: dict) -> list[dict]:
    text = (item.get("feedback_text") or "").lower()
    category = item.get("feedback_category")
    artifact = item.get("artifact_type")
    section = resolve_section(item.get("section_name"), text)

    # Visual feedback.
    if category == FeedbackCategory.VISUAL_CHANGE.value or artifact == ArtifactType.VISUAL.value:
        if "cover" in text:
            return [{"type": "regenerate_cover"}]
        slide = _slide_number(text)
        if slide:
            return [{"type": "regenerate_carousel_slide", "slide_number": slide}]
        return [{"type": "regenerate_cover"}]

    # LinkedIn feedback.
    if artifact == ArtifactType.LINKEDIN_POST.value or "linkedin" in text:
        return [{"type": "regenerate_linkedin"}]

    # Source replacement.
    if category == FeedbackCategory.SOURCE_ISSUE.value or "replace" in text:
        target = section or "research"
        return [{"type": "replace_article_and_regenerate_section", "section": target}]

    # Cross-cutting QA emphasis (no single section).
    if section is None and any(k in text for k in ("qa angle", "more qa", "testing angle", "more testing")):
        return [
            {"type": "regenerate_section", "section": "testing"},
            {"type": "regenerate_section", "section": "top_stories"},
        ]

    # Default: regenerate the resolved (or best-guess) section.
    return [{"type": "regenerate_section", "section": section or "top_stories"}]


def build_plan(items: list[dict]) -> dict:
    actions: list[dict] = []
    seen: set = set()
    for item in items:
        if item.get("feedback_category") == FeedbackCategory.APPROVAL_COMMENT.value:
            continue
        for action in _action_for(item):
            key = (action["type"], action.get("section"), action.get("slide_number"))
            if key not in seen:
                seen.add(key)
                action["reason"] = item.get("feedback_text", "")[:200]
                actions.append(action)
    plan = {"actions": actions, "action_count": len(actions)}
    logger.info("regeneration_plan_created", action_count=len(actions))
    return plan
