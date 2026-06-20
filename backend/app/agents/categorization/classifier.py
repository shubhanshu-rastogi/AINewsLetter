"""Heuristic article classifier.

Scores each newsletter section by keyword hits (biased toward the source's
default section) and elects primary/secondary categories + section.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents import taxonomy
from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection as NS


@dataclass(slots=True)
class ClassificationResult:
    primary_category: str
    secondary_category: str | None
    newsletter_section: NS
    topics: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


def _article_text(article: CollectedArticle) -> str:
    parts = [article.title or "", article.summary or "", (article.raw_content or "")[:5000]]
    return " ".join(parts).lower()


def _section_scores(text: str, article: CollectedArticle) -> list[tuple[NS, int]]:
    scores = {section: taxonomy.count_hits(text, kws) for section, kws in taxonomy.SECTION_KEYWORDS.items()}
    # Bias toward the source's assigned section.
    if article.newsletter_section is not None:
        scores[article.newsletter_section] = scores.get(article.newsletter_section, 0) + 1
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def classify(article: CollectedArticle) -> ClassificationResult:
    text = _article_text(article)
    ordered = _section_scores(text, article)

    top_section = ordered[0][0] if ordered[0][1] > 0 else (article.newsletter_section or NS.AGENTIC_AI_ENGINEERING)
    secondary = None
    if len(ordered) > 1 and ordered[1][1] > 0 and ordered[1][0] != top_section:
        secondary = taxonomy.SECTION_CATEGORY[ordered[1][0]]

    keywords = generate_tags(text)
    topics = [taxonomy.SECTION_CATEGORY[s] for s, hits in ordered if hits > 0][:3]
    if not topics:
        topics = [taxonomy.SECTION_CATEGORY[top_section]]

    return ClassificationResult(
        primary_category=taxonomy.SECTION_CATEGORY[top_section],
        secondary_category=secondary,
        newsletter_section=top_section,
        topics=topics,
        keywords=keywords,
    )


def generate_tags(text: str) -> list[str]:
    return [tag for tag, triggers in taxonomy.TAG_KEYWORDS.items() if any(trigger in text for trigger in triggers)]
