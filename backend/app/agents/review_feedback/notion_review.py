"""Notion review page integration (with internal-only fallback).

If ``NOTION_API_KEY`` is missing, :func:`create_review_page` returns ``None`` and
the platform falls back to the internal API review package. API keys are read
from settings and never returned to clients.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("review.notion")

_NOTION_API = "https://api.notion.com/v1/pages"
_NOTION_VERSION = "2022-06-28"


def _summarize(package: dict) -> str:
    stories = package.get("newsletter_draft", {}).get("top_stories", [])
    leads = "; ".join(s.get("headline", "") for s in stories[:3])
    return (
        f"{package.get('title')} · Issue {package.get('issue_number')}\n"
        f"Top stories: {leads}\n"
        f"Avg confidence: {package.get('fact_check', {}).get('average_confidence_score')}\n"
        f"Approve via: {', '.join(package.get('approval_options', []))}"
    )


async def _notion_create_page(payload: dict) -> str:
    """POST a page to Notion. Mocked in tests."""
    headers = {
        "Authorization": f"Bearer {settings.NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_NOTION_API, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json().get("url", "")


async def create_review_page(package: dict) -> str | None:
    """Create a Notion review page; return its URL, or None if not configured."""
    if not settings.NOTION_API_KEY or not settings.NOTION_REVIEW_DATABASE_ID:
        logger.info("notion_fallback", reason="not_configured")
        return None
    payload = {
        "parent": {"database_id": settings.NOTION_REVIEW_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": f"Review: {package.get('title')}"}}]},
        },
        "children": [
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": _summarize(package)}}]},
            }
        ],
    }
    try:
        url = await _notion_create_page(payload)
        logger.info("notion_page_created", url=url)
        return url
    except Exception as exc:  # noqa: BLE001 - fall back to internal review
        logger.warning("notion_create_failed_fallback", error=str(exc))
        return None
