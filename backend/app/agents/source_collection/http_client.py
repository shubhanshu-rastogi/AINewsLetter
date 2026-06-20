"""HTTP utilities for collectors.

Centralizes fetching with timeouts, retries, and a best-effort robots.txt
check. Tests monkeypatch :func:`fetch_bytes` / :func:`fetch_text` to avoid real
network access.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.agents.source_collection.exceptions import FetchError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("collection.http")

_USER_AGENT = "AINewsletterBot/0.1 (+https://github.com/shubhanshu-rastogi/AINewsLetter)"


async def fetch_bytes(
    url: str,
    *,
    timeout: float | None = None,
    retries: int | None = None,
) -> bytes:
    """Fetch a URL and return raw bytes, retrying transient failures."""
    timeout = timeout if timeout is not None else settings.COLLECTION_TIMEOUT
    retries = retries if retries is not None else settings.MAX_RETRIES
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            logger.warning("fetch_retry", url=url, attempt=attempt, max=retries, error=str(exc))
            if attempt < retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

    raise FetchError(f"Failed to fetch {url}: {last_error}")


async def fetch_text(
    url: str,
    *,
    timeout: float | None = None,
    retries: int | None = None,
) -> str:
    content = await fetch_bytes(url, timeout=timeout, retries=retries)
    return content.decode("utf-8", errors="replace")


async def is_allowed_by_robots(url: str) -> bool:
    """Best-effort robots.txt check. Defaults to allow if it cannot be fetched."""
    if not settings.RESPECT_ROBOTS_TXT:
        return True
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    try:
        body = await fetch_text(robots_url, retries=1)
    except FetchError:
        return True  # no robots.txt reachable -> allow
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    return parser.can_fetch(_USER_AGENT, url)
