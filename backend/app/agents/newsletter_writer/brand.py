"""Brand voice management for the newsletter."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings


@dataclass(slots=True)
class BrandVoice:
    name: str
    tagline: str
    audience: str = (
        "QA Leaders, Test Managers, Engineering Leaders, and IT Professionals"
    )
    tone: list[str] = field(
        default_factory=lambda: [
            "professional", "insightful", "technical", "practical",
            "leadership-oriented", "no hype", "no clickbait",
        ]
    )
    style: list[str] = field(
        default_factory=lambda: [
            "concise", "opinionated but evidence-based",
            "business-friendly", "easy to skim",
        ]
    )

    def voice_guidelines(self) -> str:
        """Compact style guide used as LLM context (when LLM polish is enabled)."""
        return (
            f"You are the editor of '{self.name}'. Audience: {self.audience}. "
            f"Tone: {', '.join(self.tone)}. Style: {', '.join(self.style)}. "
            "Avoid sensational headlines, marketing language, and unsupported claims."
        )


def load_brand() -> BrandVoice:
    return BrandVoice(name=settings.NEWSLETTER_NAME, tagline=settings.NEWSLETTER_TAGLINE)
