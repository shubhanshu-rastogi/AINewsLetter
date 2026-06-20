"""LinkedIn publishing channel (announcement post + carousel).

Simulated by default; real HTTP path isolated in ``_linkedin_request``.
"""

from __future__ import annotations

import uuid

import httpx

from app.agents.publishing.exceptions import PermanentPublishError, RetryablePublishError
from app.agents.publishing.types import PublishResult
from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import PublishState

logger = get_logger("publishing.linkedin")

_LINKEDIN_API = "https://api.linkedin.com/v2"
_DEFAULT_HASHTAGS = ["#AI", "#QualityEngineering", "#Testing", "#AgenticAI"]


def build_post_payload(package: dict) -> dict:
    linkedin = package.get("linkedin_post") or {}
    return {
        "author": settings.LINKEDIN_AUTHOR_URN,
        "text": linkedin.get("body", ""),
        "hashtags": linkedin.get("hashtags") or _DEFAULT_HASHTAGS,
    }


def build_carousel_payload(package: dict) -> dict:
    return {
        "author": settings.LINKEDIN_AUTHOR_URN,
        "slides": package.get("carousel_outline") or [],
        "visuals": [v for v in package.get("visuals", []) if v.get("visual_kind") == "carousel_slide"],
    }


async def _linkedin_request(endpoint: str, payload: dict) -> str:
    headers = {"Authorization": f"Bearer {settings.LINKEDIN_CLIENT_SECRET}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{_LINKEDIN_API}/{endpoint}", headers=headers, json=payload)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryablePublishError(f"LinkedIn transient error {resp.status_code}")
        if resp.status_code in (401, 403):
            raise PermanentPublishError("LinkedIn authentication failed")
        resp.raise_for_status()
        return resp.json().get("id", "")


async def _simulate(kind: str) -> PublishResult:
    external_id = f"linkedin-{kind}-sim-{uuid.uuid4().hex[:12]}"
    logger.info("linkedin_publication_completed", simulated=True, kind=kind, external_id=external_id)
    return PublishResult(
        success=True,
        channel="linkedin",
        status=PublishState.PUBLISHED,
        external_id=external_id,
        metadata={"simulated": True, "kind": kind},
    )


async def publish_post(package: dict) -> PublishResult:
    logger.info("linkedin_publication_started", kind="post")
    if not settings.ENABLE_REAL_PUBLISHING or not settings.LINKEDIN_CLIENT_SECRET:
        return await _simulate("post")
    try:
        external_id = await _linkedin_request("ugcPosts", build_post_payload(package))
    except httpx.TimeoutException as exc:
        raise RetryablePublishError(f"LinkedIn timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RetryablePublishError(f"LinkedIn network error: {exc}") from exc
    logger.info("linkedin_publication_completed", kind="post", external_id=external_id)
    return PublishResult(
        success=True,
        channel="linkedin",
        status=PublishState.PUBLISHED,
        external_id=external_id,
        metadata={"simulated": False, "kind": "post"},
    )


async def publish_carousel(package: dict) -> PublishResult:
    logger.info("linkedin_publication_started", kind="carousel")
    if not settings.ENABLE_REAL_PUBLISHING or not settings.LINKEDIN_CLIENT_SECRET:
        return await _simulate("carousel")
    try:
        external_id = await _linkedin_request("assets", build_carousel_payload(package))
    except httpx.TimeoutException as exc:
        raise RetryablePublishError(f"LinkedIn timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RetryablePublishError(f"LinkedIn network error: {exc}") from exc
    logger.info("linkedin_publication_completed", kind="carousel", external_id=external_id)
    return PublishResult(
        success=True,
        channel="linkedin",
        status=PublishState.PUBLISHED,
        external_id=external_id,
        metadata={"simulated": False, "kind": "carousel"},
    )
