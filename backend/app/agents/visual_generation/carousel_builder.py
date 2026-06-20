"""Builds the 10-slide LinkedIn carousel from newsletter content."""

from __future__ import annotations

from PIL import Image

from app.agents.visual_generation import card_renderer
from app.agents.visual_generation.brand_config import BrandConfig


def _body_from(item, *keys: str, default: str = "") -> str:
    if isinstance(item, dict):
        for k in keys:
            if item.get(k):
                return item[k]
    if isinstance(item, list) and item:
        first = item[0]
        if isinstance(first, dict):
            for k in keys:
                if first.get(k):
                    return first[k]
    return default


def build_slide_specs(content: dict, brand: BrandConfig) -> list[dict]:
    """Return exactly 10 slide specs following the required structure."""
    stories = content.get("top_stories", [])
    tools = content.get("tools", [])

    def story_title(idx, default):
        return stories[idx]["headline"] if len(stories) > idx else default

    return [
        {"label": "Issue", "title": brand.logo_text, "body": brand.tagline},
        {
            "label": "This Week's Big Picture",
            "title": "The big picture",
            "body": content.get("executive_summary", "Your weekly AI engineering briefing."),
        },
        {
            "label": "Agentic AI Engineering",
            "title": story_title(0, "Top agentic AI story"),
            "body": _body_from(stories, "what_happened", default="See this week's issue."),
        },
        {
            "label": "AI Evaluation & QA Gates",
            "title": "Evaluation & QA gates",
            "body": _body_from(content.get("testing"), "insight", default="Evaluation and quality gates in focus."),
        },
        {
            "label": "AI Testing & Quality",
            "title": "Quality engineering insight",
            "body": _body_from(
                content.get("testing"), "insight", "recommendation", default="Fold AI testing into your quality gates."
            ),
        },
        {
            "label": "AI Tools Worth Watching",
            "title": _body_from(tools, "name", default="Tools worth watching"),
            "body": _body_from(tools, "what_it_does", default="New tooling for AI engineering teams."),
        },
        {
            "label": "Research Watch",
            "title": _body_from(content.get("research"), "paper", default="Research watch"),
            "body": _body_from(content.get("research"), "key_findings", default="Notable research this week."),
        },
        {
            "label": "Coding Agent Benchmark",
            "title": _body_from(content.get("benchmark"), "title", default="Benchmark watch"),
            "body": _body_from(content.get("benchmark"), "what_improved", default="Coding agent progress and gaps."),
        },
        {
            "label": "Weekly Trend Signals",
            "title": "Trend signals",
            "body": _body_from(content.get("trends"), "signal", default="Signals shaping AI engineering."),
        },
        {
            "label": "Final Takeaways",
            "title": "Takeaways + subscribe",
            "body": " • ".join(content.get("final_takeaways", [])[:3]) or "Subscribe for weekly AI + QE insights.",
        },
    ]


def render_slide(brand: BrandConfig, spec: dict, slide_number: int, issue: int | None, size) -> Image.Image:
    return card_renderer.render_card(
        brand,
        size=size,
        label=spec["label"],
        title=spec["title"],
        body=spec["body"],
        footer_left=brand.footer_text,
        footer_right=f"Issue {issue}",
        badge=f"{slide_number}/10",
    )
