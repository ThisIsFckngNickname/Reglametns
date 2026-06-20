"""
Cache service with Redis + in-memory fallback.

When Redis is enabled and connected, operations delegate to Redis.
Otherwise an in-memory dict is used (process-local, lost on restart).
"""

from typing import Any, Optional

from app.services.redis_service import RedisService


class CacheService:
    """Unified cache service backed by Redis or in-memory dict."""

    def __init__(self, redis_service: Optional[RedisService] = None):
        self._redis = redis_service
        self._memory: dict[str, str] = {}  # fallback in-memory

    async def get(self, key: str) -> Optional[str]:
        """Get value by key. Returns None if missing."""
        if self._redis and self._redis.enabled:
            return await self._redis.cache_get(key)
        return self._memory.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 300):
        """Set value with optional TTL (seconds)."""
        if self._redis and self._redis.enabled:
            await self._redis.cache_set(key, value, ttl_seconds)
        self._memory[key] = value

    async def delete(self, key: str):
        """Delete a key from cache."""
        if self._redis and self._redis.enabled:
            await self._redis.cache_delete(key)
        self._memory.pop(key, None)
