"""
Tests for Redis service.

Requires a running Redis instance when REDIS_URL env var is set.
When Redis is not available, in-memory fallback is tested instead.
"""

import os

import pytest

from app.services.redis_service import RedisService


# ─── Redis-backed tests (require REDIS_URL) ────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("REDIS_URL"),
    reason="Redis tests require REDIS_URL env var",
)
@pytest.mark.asyncio
class TestRedisService:
    """Tests that require a real Redis connection."""

    async def test_connect_and_ping(self):
        svc = RedisService()
        await svc.connect()
        assert svc.enabled
        await svc.disconnect()
        assert not svc.enabled

    async def test_cache_set_get(self):
        svc = RedisService()
        await svc.connect()
        try:
            await svc.cache_set("test:val", "hello", ttl_seconds=10)
            val = await svc.cache_get("test:val")
            assert val == "hello"

            # Cache miss
            missing = await svc.cache_get("test:nonexistent")
            assert missing is None
        finally:
            await svc.cache_delete("test:val")
            await svc.disconnect()

    async def test_cache_ttl(self):
        svc = RedisService()
        await svc.connect()
        try:
            await svc.cache_set("test:ttl", "expires", ttl_seconds=1)
            val = await svc.cache_get("test:ttl")
            assert val == "expires"
            # We don't actually wait for expiration in tests
            # Just verify the key exists
        finally:
            await svc.cache_delete("test:ttl")
            await svc.disconnect()

    async def test_cache_delete(self):
        svc = RedisService()
        await svc.connect()
        try:
            await svc.cache_set("test:del", "todelete", ttl_seconds=60)
            await svc.cache_delete("test:del")
            val = await svc.cache_get("test:del")
            assert val is None
        finally:
            await svc.disconnect()

    async def test_rate_limit_allowed(self):
        svc = RedisService()
        await svc.connect()
        try:
            await svc.rate_limit_reset("test:rl:allowed")
            allowed, remaining, reset_at = await svc.rate_limit_check(
                "test:rl:allowed", max_attempts=3, window_seconds=60,
            )
            assert allowed is True
            assert remaining == 2
            assert reset_at is None
        finally:
            await svc.rate_limit_reset("test:rl:allowed")
            await svc.disconnect()

    async def test_rate_limit_exceeded(self):
        svc = RedisService()
        await svc.connect()
        key = "test:rl:exceed"
        try:
            await svc.rate_limit_reset(key)
            # Use all 3 attempts
            for i in range(3):
                allowed, remaining, _ = await svc.rate_limit_check(
                    key, max_attempts=3, window_seconds=60,
                )
                assert allowed is True
                assert remaining == 2 - i

            # 4th attempt should be blocked
            allowed, remaining, reset_at = await svc.rate_limit_check(
                key, max_attempts=3, window_seconds=60,
            )
            assert allowed is False
            assert remaining == 0
            assert reset_at is not None
            assert isinstance(reset_at, int)
        finally:
            await svc.rate_limit_reset(key)
            await svc.disconnect()

    async def test_rate_limit_reset(self):
        svc = RedisService()
        await svc.connect()
        key = "test:rl:reset"
        try:
            await svc.rate_limit_reset(key)
            await svc.rate_limit_check(key, max_attempts=1, window_seconds=60)
            # After reset, should be allowed again
            await svc.rate_limit_reset(key)
            allowed, remaining, _ = await svc.rate_limit_check(
                key, max_attempts=1, window_seconds=60,
            )
            assert allowed is True
            assert remaining == 0  # 1 attempt used, 0 remaining
        finally:
            await svc.rate_limit_reset(key)
            await svc.disconnect()


# ─── In-memory fallback tests (always run) ─────────────────────────────────


class TestMemoryFallback:
    """Tests with Redis disabled (no REDIS_URL)."""

    async def test_redis_disabled_by_default(self):
        """When no REDIS_URL, RedisService should be disabled."""
        svc = RedisService()
        # Without connect, enabled should be False
        assert svc.enabled is False

    async def test_rate_limit_unlimited_when_disabled(self):
        """Rate limit returns unlimited when Redis is disabled."""
        svc = RedisService()
        allowed, remaining, reset_at = await svc.rate_limit_check("any-key")
        assert allowed is True
        assert remaining == 999
        assert reset_at is None

    async def test_cache_get_returns_none_when_disabled(self):
        """Cache returns None when Redis is disabled."""
        svc = RedisService()
        val = await svc.cache_get("any-key")
        assert val is None

    async def test_cache_set_noop_when_disabled(self):
        """Cache set is a no-op when Redis is disabled (no error)."""
        svc = RedisService()
        # Should not raise
        await svc.cache_set("key", "value", 10)
        await svc.cache_delete("key")
        await svc.rate_limit_reset("key")

    async def test_redis_property_raises_when_disabled(self):
        """Accessing .redis when disabled should raise."""
        svc = RedisService()
        with pytest.raises(RuntimeError, match="not connected or disabled"):
            _ = svc.redis
