"""LangGraph workflow state definition (placeholder).

Declares the typed state object that will flow through the agent graph. The
graph itself and node logic are NOT implemented in the foundation phase.
"""

from __future__ import annotations

from typing import Any, TypedDict


class NewsletterState(TypedDict, total=False):
    """State carried through the newsletter generation graph.

    Fields are intentionally permissive (``total=False``) during the foundation
    phase and will be tightened as agents are implemented.
    """

    run_id: str
    collected_articles: list[dict[str, Any]]
    relevant_articles: list[dict[str, Any]]
    categorized_articles: dict[str, list[dict[str, Any]]]
    fact_checks: list[dict[str, Any]]
    draft_sections: list[dict[str, Any]]
    linkedin_posts: list[dict[str, Any]]
    visual_assets: list[dict[str, Any]]
    review_decision: str | None
    feedback: list[dict[str, Any]]
    errors: list[str]
