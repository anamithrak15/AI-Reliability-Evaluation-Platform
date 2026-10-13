"""Fixed-window rate limiting backed by Redis. Fails open so a Redis outage never takes the API down."""

import logging
import time
from typing import Protocol

import redis

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class Counter(Protocol):
    def incr(self, key: str, ttl: int) -> int: ...


class RedisCounter:
    def __init__(self, client: redis.Redis):
        self._client = client

    def incr(self, key: str, ttl: int) -> int:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        return int(pipe.execute()[0])


class RateLimiter:
    def __init__(self, counter: Counter, window_seconds: int = 60, clock=time.time):
        self._counter = counter
        self._window = window_seconds
        self._clock = clock

    def check(self, bucket: str, client: str, limit: int) -> tuple[bool, int]:
        """(allowed, retry_after_seconds). A limit <= 0 disables the bucket."""
        if limit <= 0:
            return True, 0
        now = int(self._clock())
        window_id = now // self._window
        retry_after = self._window - now % self._window
        try:
            count = self._counter.incr(f"ratelimit:{bucket}:{client}:{window_id}", self._window + 1)
        except Exception:
            logger.warning("rate limiter unavailable; allowing request", exc_info=True)
            return True, 0
        return count <= limit, retry_after


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        settings = get_settings()
        client = redis.Redis.from_url(
            settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
        )
        _limiter = RateLimiter(RedisCounter(client), settings.rate_limit_window_seconds)
    return _limiter


def enforce(bucket: str, key: str, limit: int) -> None:
    """Raise 429 when `key` has used up `limit` hits of `bucket` in the current window."""
    if not get_settings().rate_limit_enabled:
        return
    allowed, _ = get_limiter().check(bucket, key, limit)
    if not allowed:
        raise AppError(429, "rate_limited", "Too many attempts; wait a minute and try again")
