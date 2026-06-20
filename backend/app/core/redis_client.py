"""Redis abstraction with an in-memory fallback.

In development (or when ``ENABLE_REDIS`` is off / Redis is unreachable) the app
transparently uses an in-process fake so it remains fully functional without a
Redis server. The same async interface is used for caching, rate limiting,
locks, and retry coordination.
"""

from __future__ import annotations

import time
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("redis")


class RedisLike(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...
    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool: ...
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> bool: ...
    async def ttl(self, key: str) -> int: ...
    async def delete(self, key: str) -> int: ...
    async def ping(self) -> bool: ...


class InMemoryRedis:
    """Process-local fake implementing the subset of Redis the app uses."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._expiry: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is not None and exp < time.time():
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> str | None:
        if self._expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        if ex is not None:
            self._expiry[key] = time.time() + ex
        return True

    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool:
        if not self._expired(key) and key in self._store:
            return False
        await self.set(key, value, ex)
        return True

    async def incr(self, key: str) -> int:
        if self._expired(key):
            current = 0
        else:
            current = int(self._store.get(key, "0"))
        current += 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._store:
            self._expiry[key] = time.time() + seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        exp = self._expiry.get(key)
        if exp is None:
            return -1
        return max(0, int(exp - time.time()))

    async def delete(self, key: str) -> int:
        existed = key in self._store
        self._store.pop(key, None)
        self._expiry.pop(key, None)
        return 1 if existed else 0

    async def ping(self) -> bool:
        return True


_client: RedisLike | None = None
_is_real_redis = False


async def get_redis() -> RedisLike:
    """Return the shared Redis client (real if configured, else in-memory)."""
    global _client, _is_real_redis
    if _client is not None:
        return _client

    if settings.ENABLE_REDIS and settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            _client = client
            _is_real_redis = True
            logger.info("redis_connected", url=settings.REDIS_URL)
            return _client
        except Exception as exc:  # noqa: BLE001 - degrade gracefully to in-memory
            logger.warning("redis_unavailable_fallback", error=str(exc))

    _client = InMemoryRedis()
    _is_real_redis = False
    return _client


def is_real_redis() -> bool:
    return _is_real_redis


async def reset_redis() -> None:
    """Reset the cached client (used by tests)."""
    global _client, _is_real_redis
    _client = None
    _is_real_redis = False
