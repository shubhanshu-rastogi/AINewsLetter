"""Article selection rules.

Applies the editorial quota (top stories + per-section picks) over ranked
articles, avoiding selecting two articles from the same canonical story.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection as NS

MAX_STORIES = 5
MAX_TOOLS = 3

# Single-pick section quotas.
SECTION_QUOTA: dict[NS, int] = {
    NS.RESEARCH_WATCH: 1,
    NS.ENTERPRISE_AI_ADOPTION: 1,
    NS.AI_TESTING_QUALITY: 1,
    NS.CODING_AGENT_BENCHMARK: 1,
}


@dataclass(slots=True)
class SelectionResult:
    selected: list[CollectedArticle] = field(default_factory=list)
    category_map: dict[str, list[str]] = field(default_factory=dict)


def select_articles(ranked: Sequence[CollectedArticle]) -> SelectionResult:
    """Select newsletter candidates from a ranked list."""
    result = SelectionResult()
    used_stories: set = set()

    def story_key(article: CollectedArticle):
        return article.canonical_story_id or article.id

    def take(article: CollectedArticle) -> bool:
        key = story_key(article)
        if key in used_stories:
            return False
        used_stories.add(key)
        article.is_selected = True
        result.selected.append(article)
        section = article.newsletter_section.value if article.newsletter_section else "uncategorized"
        result.category_map.setdefault(section, []).append(str(article.id))
        return True

    # 1) Top major stories (any section).
    stories = 0
    for article in ranked:
        if stories >= MAX_STORIES:
            break
        if take(article):
            stories += 1

    # 2) Top tools.
    tools = 0
    for article in ranked:
        if tools >= MAX_TOOLS:
            break
        if article.newsletter_section == NS.AI_TOOLS_WATCH and take(article):
            tools += 1

    # 3) Single-pick sections (research, enterprise, qa, coding-agent).
    for section, quota in SECTION_QUOTA.items():
        picked = 0
        for article in ranked:
            if picked >= quota:
                break
            if article.newsletter_section == section and take(article):
                picked += 1

    return result
