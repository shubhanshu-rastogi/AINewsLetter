"""Feedback interpretation: classify a feedback item into actionable metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.models.enums import ArtifactType, FeedbackCategory, FeedbackSeverity

logger = get_logger("feedback.classifier")

# Keyword -> feedback category (first match wins, ordered by specificity).
_CATEGORY_RULES: list[tuple[FeedbackCategory, tuple[str, ...]]] = [
    (FeedbackCategory.APPROVAL_COMMENT, ("looks good", "approve", "ship it", "lgtm")),
    (FeedbackCategory.FACT_CHECK_ISSUE, ("inaccurate", "wrong", "false", "fact", "confidence", "unverified")),
    (FeedbackCategory.SOURCE_ISSUE, ("source", "citation", "replace the", "replace article", "different article")),
    (FeedbackCategory.VISUAL_CHANGE, ("visual", "slide", "image", "cover", "carousel", "graphic")),
    (FeedbackCategory.LENGTH_CHANGE, ("shorter", "longer", "length", "trim", "expand", "concise", "too long", "too short")),
    (FeedbackCategory.TONE_CHANGE, ("tone", "voice", "formal", "casual", "punchy", "hype")),
    (FeedbackCategory.STRUCTURE_CHANGE, ("structure", "reorder", "move", "order", "rearrange")),
]
_BLOCKER_SIGNALS = ("do not publish", "must not", "fabricated", "legal", "wrong")
_HIGH_SIGNALS = ("must", "required", "important", "replace")


@dataclass(slots=True)
class Classification:
    artifact_type: str
    section_name: str | None
    feedback_category: str
    severity: str
    action_required: str
    regeneration_needed: bool


def _category(text: str) -> FeedbackCategory:
    low = text.lower()
    for category, keywords in _CATEGORY_RULES:
        if any(k in low for k in keywords):
            return category
    return FeedbackCategory.CONTENT_CHANGE


def _severity(text: str, provided: str | None) -> FeedbackSeverity:
    if provided:
        try:
            return FeedbackSeverity(provided.lower())
        except ValueError:
            pass
    low = text.lower()
    if any(s in low for s in _BLOCKER_SIGNALS):
        return FeedbackSeverity.BLOCKER
    if any(s in low for s in _HIGH_SIGNALS):
        return FeedbackSeverity.HIGH
    return FeedbackSeverity.MEDIUM


def classify(item: dict) -> Classification:
    """Classify a single feedback item dict."""
    text = item.get("feedback_text", "") or ""
    artifact = item.get("artifact_type") or ArtifactType.NEWSLETTER.value
    category = _category(text)
    severity = _severity(text, item.get("severity"))
    regeneration_needed = category != FeedbackCategory.APPROVAL_COMMENT

    action = {
        FeedbackCategory.LENGTH_CHANGE: "Regenerate the affected section with revised length",
        FeedbackCategory.TONE_CHANGE: "Regenerate the affected section in the requested tone",
        FeedbackCategory.STRUCTURE_CHANGE: "Regenerate/reorder the affected section",
        FeedbackCategory.VISUAL_CHANGE: "Regenerate the affected visual",
        FeedbackCategory.SOURCE_ISSUE: "Replace the source and regenerate the section",
        FeedbackCategory.FACT_CHECK_ISSUE: "Re-verify and regenerate the affected content",
        FeedbackCategory.APPROVAL_COMMENT: "No regeneration required",
        FeedbackCategory.CONTENT_CHANGE: "Regenerate the affected section",
    }[category]

    result = Classification(
        artifact_type=artifact,
        section_name=item.get("section_name"),
        feedback_category=category.value,
        severity=severity.value,
        action_required=action,
        regeneration_needed=regeneration_needed,
    )
    logger.info("feedback_classified", category=category.value, severity=severity.value)
    return result
