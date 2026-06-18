"""Tag and topic generation helpers (heuristic)."""

from __future__ import annotations

from app.agents import taxonomy
from app.agents.categorization.classifier import generate_tags
from app.models.collected_article import CollectedArticle


def _article_text(article: CollectedArticle) -> str:
    parts = [article.title or "", article.summary or "", (article.raw_content or "")[:5000]]
    return " ".join(parts).lower()


def tags_for(article: CollectedArticle) -> list[str]:
    return generate_tags(_article_text(article))


def topics_for(article: CollectedArticle) -> list[str]:
    text = _article_text(article)
    topics = [
        taxonomy.SECTION_CATEGORY[section]
        for section, kws in taxonomy.SECTION_KEYWORDS.items()
        if taxonomy.count_hits(text, kws) > 0
    ]
    return topics[:3]
