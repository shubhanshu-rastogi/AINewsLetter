"""Retry manager: exponential backoff for transient publish failures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.agents.publishing.exceptions import PermanentPublishError, RetryablePublishError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("publishing.retry")

T = TypeVar("T")


def backoff_delay(attempt: int, base: float | None = None) -> float:
    """Exponential backoff: base * 2**(attempt-1)."""
    base = base if base is not None else settings.PUBLISH_RETRY_BASE_DELAY
    return base * (2 ** max(attempt - 1, 0))


def is_retryable(exc: Exception) -> bool:
    return isinstance(exc, RetryablePublishError)


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int | None = None,
) -> T:
    """Run an async operation, retrying transient failures with backoff.

    Permanent failures (config/auth/missing assets) are never retried.
    """
    max_retries = max_retries if max_retries is not None else settings.MAX_PUBLISH_RETRIES
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except PermanentPublishError:
            raise  # do not retry
        except RetryablePublishError as exc:
            last_error = exc
            logger.warning("publish_retry", attempt=attempt, max=max_retries, error=str(exc))
            if attempt < max_retries:
                await asyncio.sleep(backoff_delay(attempt))
    raise last_error if last_error else RetryablePublishError("retry exhausted")
