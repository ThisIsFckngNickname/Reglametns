"""
Async Redis service with connection pool.

Provides:
- Cache operations (get/set/delete with TTL)
- Rate limiting via sorted sets (sliding window)
- Graceful fallback when Redis is disabled/not available
"""

from typing import Any, Optional

from redis.asyncio import Redis as AsyncRedis

from app.config import settings


class RedisService:
    """Async Redis service with connection pool."""

    def __init__(self):
        self._redis: Optional[AsyncRedis] = None
        self._enabled = settings.redis_enabled

    async def connect(self):
        """Open connection to Redis."""
        if not self._enabled:
            return
        self._redis = AsyncRedis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )

    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def redis(self) -> AsyncRedis:
        """Get the Redis client. Raises RuntimeError if not connected/disabled."""
        if not self._enabled or not self._redis:
            raise RuntimeError("Redis not connected or disabled")
        return self._redis

    @property
    def enabled(self) -> bool:
        """Check if Redis is enabled and connected."""
        return self._enabled and self._redis is not None

    # ─── Cache ──────────────────────────────────────────────────────────────

    async def cache_get(self, key: str) -> Optional[str]:
        """Get a value from cache by key. Returns None if missing or Redis disabled."""
        if not self.enabled:
            return None
        return await self.redis.get(f"cache:{key}")

    async def cache_set(self, key: str, value: str, ttl_seconds: int = 300):
        """Set a cache value with TTL. No-op if Redis disabled."""
        if not self.enabled:
            return
        await self.redis.setex(f"cache:{key}", ttl_seconds, value)

    async def cache_delete(self, key: str):
        """Delete a cache key. No-op if Redis disabled."""
        if not self.enabled:
            return
        await self.redis.delete(f"cache:{key}")

    # ─── Rate Limiting ──────────────────────────────────────────────────────

    async def rate_limit_check(
        self,
        key: str,
        max_attempts: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> tuple[bool, int, Optional[int]]:
        """
        Check rate limit for *key* using a sorted-set sliding window.

        Redis key format: ``ratelimit:{key}``

        Returns:
            (is_allowed, remaining, reset_timestamp)

        - ``is_allowed`` — True if the request is within limits
        - ``remaining`` — remaining attempts in current window
        - ``reset_timestamp`` — Unix timestamp when the window resets (None if
          no limit hit or rate limiting is disabled)

        When Redis is disabled returns ``(True, 999, None)`` (unlimited).
        """
        if not self.enabled:
            return True, 999, None  # unlimited in disabled mode

        max_attempts = max_attempts or settings.rate_limit_max_attempts
        window_seconds = window_seconds or settings.rate_limit_window_seconds

        redis_key = f"ratelimit:{key}"
        now = await self.redis.time()  # Redis time (seconds, microseconds)

        # Clean expired entries and count remaining in a pipeline
        pipe = self.redis.pipeline()
        await pipe.zremrangebyscore(redis_key, 0, now[0] - window_seconds)
        await pipe.zcard(redis_key)
        results = await pipe.execute()
        count = results[1] if results[1] else 0

        if count >= max_attempts:
            # Get oldest entry to calculate reset timestamp
            oldest = await self.redis.zrange(redis_key, 0, 0, withscores=True)
            reset_at = int(oldest[0][1]) + window_seconds if oldest else int(now[0]) + window_seconds
            return False, 0, reset_at

        # Record current attempt
        await self.redis.zadd(redis_key, {str(now[0]): now[0]})
        await self.redis.expire(redis_key, window_seconds * 2)  # safety TTL

        remaining = max_attempts - count - 1
        return True, remaining, None

    async def rate_limit_reset(self, key: str):
        """Remove all rate-limit entries for *key*."""
        if not self.enabled:
            return
        await self.redis.delete(f"ratelimit:{key}")
