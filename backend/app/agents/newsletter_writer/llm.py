"""Optional LLM polish for newsletter prose.

Disabled by default (``ENABLE_LLM_WRITER=false``). Isolated so tests can mock
:func:`polish_text` without any network calls.
"""

from __future__ import annotations

from app.agents.newsletter_writer.brand import BrandVoice
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("writer.llm")


async def polish_text(text: str, brand: BrandVoice) -> str:
    """Rewrite text in brand voice via an LLM. Returns input unchanged on failure."""
    try:
        if settings.LLM_PROVIDER == "openai":
            return await _openai_polish(text, brand)
        return await _anthropic_polish(text, brand)
    except Exception as exc:  # noqa: BLE001 - polish is best-effort
        logger.warning("polish_failed", error=str(exc))
        return text


async def _anthropic_polish(text: str, brand: BrandVoice) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1024,
        system=brand.voice_guidelines(),
        messages=[{"role": "user", "content": f"Polish this newsletter copy:\n\n{text}"}],
    )
    return message.content[0].text


async def _openai_polish(text: str, brand: BrandVoice) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": brand.voice_guidelines()},
            {"role": "user", "content": f"Polish this newsletter copy:\n\n{text}"},
        ],
    )
    return response.choices[0].message.content or text
