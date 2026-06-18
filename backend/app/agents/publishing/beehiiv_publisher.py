"""Beehiiv publishing channel.

Simulated by default (``ENABLE_REAL_PUBLISHING=false`` or no API key); the real
HTTP path is isolated in ``_beehiiv_request`` so tests can mock it.
"""

from __future__ import annotations

import uuid

import httpx

from app.agents.publishing.exceptions import PermanentPublishError, RetryablePublishError
from app.agents.publishing.types import PublishResult
from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import PublishState

logger = get_logger("publishing.beehiiv")

_BEEHIIV_API = "https://api.beehiiv.com/v2"


def build_payload(package: dict) -> dict:
    """Map a newsletter package to the Beehiiv post payload."""
    content = package.get("newsletter_draft", {})
    cover = content.get("cover", {})
    return {
        "title": package.get("title") or cover.get("title"),
        "subtitle": content.get("executive_summary", "")[:200],
        "body_content": content,
        "cover_image_url": package.get("cover_image_url"),
        "publish_date": cover.get("publication_date"),
        "tags": ["AI", "Quality Engineering", "Agentic AI"],
        "cta": {"text": "Subscribe", "url": settings.NEWSLETTER_SUBSCRIBE_URL},
    }


async def _beehiiv_request(payload: dict) -> str:
    """POST to Beehiiv; return external publication id. Mocked in tests."""
    headers = {"Authorization": f"Bearer {settings.BEEHIIV_API_KEY}"}
    url = f"{_BEEHIIV_API}/publications/{settings.BEEHIIV_PUBLICATION_ID}/posts"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryablePublishError(f"Beehiiv transient error {resp.status_code}")
        if resp.status_code in (401, 403):
            raise PermanentPublishError("Beehiiv authentication failed")
        resp.raise_for_status()
        return resp.json().get("data", {}).get("id", "")


async def publish(package: dict) -> PublishResult:
    """Publish to Beehiiv (or simulate). Raises Retryable/Permanent on failure."""
    logger.info("beehiiv_publication_started")
    if not settings.ENABLE_REAL_PUBLISHING or not settings.BEEHIIV_API_KEY:
        external_id = f"beehiiv-sim-{uuid.uuid4().hex[:12]}"
        logger.info("beehiiv_publication_completed", simulated=True, external_id=external_id)
        return PublishResult(
            success=True, channel="beehiiv", status=PublishState.PUBLISHED,
            external_id=external_id, metadata={"simulated": True},
        )

    try:
        external_id = await _beehiiv_request(build_payload(package))
    except httpx.TimeoutException as exc:
        raise RetryablePublishError(f"Beehiiv timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RetryablePublishError(f"Beehiiv network error: {exc}") from exc

    logger.info("beehiiv_publication_completed", external_id=external_id)
    return PublishResult(
        success=True, channel="beehiiv", status=PublishState.PUBLISHED,
        external_id=external_id, metadata={"simulated": False},
    )
