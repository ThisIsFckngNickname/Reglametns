import time
from collections import defaultdict
from typing import Optional

from app.config import settings
from app.services.redis_service import RedisService


class InMemoryRateLimiter:
    """Simple in-memory rate limiter based on sliding window."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float) -> None:
        """Remove expired entries for the given key."""
        cutoff = now - self.window_seconds
        self.attempts[key] = [
            t for t in self.attempts[key] if t > cutoff
        ]
        if not self.attempts[key]:
            del self.attempts[key]

    def check(self, key: str) -> tuple[bool, int, int, Optional[int]]:
        """
        Check if the request is rate-limited.
        Returns: (is_allowed, limit, remaining, reset_timestamp)
        """
        now = time.time()
        self._cleanup(key, now)

        current_count = len(self.attempts.get(key, []))
        remaining = max(0, self.max_attempts - current_count)

        if current_count >= self.max_attempts:
            # Calculate reset time from the oldest entry
            oldest = self.attempts[key][0] if self.attempts.get(key) else now
            reset_at = int(oldest + self.window_seconds)
            return False, self.max_attempts, 0, reset_at

        return True, self.max_attempts, remaining, None

    def increment(self, key: str) -> None:
        """Record an attempt for the given key."""
        now = time.time()
        self.attempts[key].append(now)

    def reset(self, key: str) -> None:
        """Clear all attempts for the given key."""
        self.attempts.pop(key, None)


class RateLimiter:
    """
    Rate limiter that delegates to Redis (when available) or in-memory.

    API matches ``InMemoryRateLimiter.check`` return signature:
    ``(is_allowed, limit, remaining, reset_timestamp)``
    but all methods are async.
    """

    def __init__(self, redis_service: Optional[RedisService] = None):
        self._redis = redis_service
        self._memory = InMemoryRateLimiter(
            max_attempts=settings.rate_limit_max_attempts,
            window_seconds=settings.rate_limit_window_seconds,
        )

    async def is_allowed(
        self,
        key: str,
        max_attempts: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> tuple[bool, int, int, Optional[int]]:
        """
        Check if the request is rate-limited and record the attempt if allowed.

        Returns: (is_allowed, limit, remaining, reset_timestamp)
        """
        max_attempts = max_attempts or settings.rate_limit_max_attempts
        window_seconds = window_seconds or settings.rate_limit_window_seconds

        if self._redis and self._redis.enabled:
            allowed, remaining, reset_at = await self._redis.rate_limit_check(
                key, max_attempts, window_seconds,
            )
            return allowed, max_attempts, remaining, reset_at

        # In-memory fallback
        allowed, limit, remaining, reset_at = self._memory.check(key)
        if allowed:
            self._memory.increment(key)
        return allowed, max_attempts, remaining, reset_at

    async def reset(self, key: str) -> None:
        """Clear all rate-limit entries for *key*."""
        if self._redis and self._redis.enabled:
            await self._redis.rate_limit_reset(key)
        self._memory.reset(key)
