"""Optional LLM-assisted classification refinement.

Disabled by default (``ENABLE_LLM_CLASSIFICATION=false``). When enabled, this
returns extra keywords/topics to merge with the heuristic result. Network calls
are isolated here so tests can mock :func:`llm_classify`.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.collected_article import CollectedArticle

logger = get_logger("categorization.llm")

_PROMPT = (
    "Classify this AI/software-engineering article. Return JSON with keys "
    "'keywords' (list of short tags) and 'topics' (list of topic labels).\n\n"
    "Title: {title}\nSummary: {summary}"
)


async def llm_classify(article: CollectedArticle) -> dict[str, Any] | None:
    """Return optional {'keywords': [...], 'topics': [...]} via an LLM, or None."""
    prompt = _PROMPT.format(title=article.title or "", summary=article.summary or "")
    try:
        if settings.LLM_PROVIDER == "openai":
            text = await _openai_complete(prompt)
        else:
            text = await _anthropic_complete(prompt)
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001 - LLM is best-effort enrichment
        logger.warning("llm_classify_failed", error=str(exc))
        return None


async def _anthropic_complete(prompt: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _openai_complete(prompt: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or "{}"
