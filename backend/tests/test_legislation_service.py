"""
Tests for Legislation Service (search, sources, caching).
"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.services.legislation_service import (
    LegislationService,
    PravoGovRuAdapter,
    TTLCache,
)
from app.schemas.legislation import LegislationSource, LegislationSearchResult


# ─── TTLCache Unit Tests ───────────────────────────────────────────

class TestTTLCache:
    """Unit tests for the TTL cache."""

    def test_get_set(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", [LegislationSearchResult(title="Test")])
        results = cache.get("key1")
        assert results is not None
        assert results[0].title == "Test"

    def test_missing_key(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_expiry(self):
        cache = TTLCache(ttl_seconds=0)  # Immediate expiry
        cache.set("key1", [LegislationSearchResult(title="Test")])
        import time
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_clear(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", [LegislationSearchResult(title="Test")])
        cache.clear()
        assert cache.get("key1") is None


# ─── Legislation Service Unit Tests ─────────────────────────────────

class TestLegislationService:
    """Unit tests for the LegislationService."""

    def test_register_adapter(self):
        service = LegislationService()
        adapter = PravoGovRuAdapter()
        service.register_adapter(adapter)
        sources = service.get_sources()
        assert len(sources) == 1
        assert sources[0].id == "pravo.gov.ru"

    def test_get_sources_empty(self):
        service = LegislationService()
        assert service.get_sources() == []

    def test_get_sources_after_register(self):
        service = LegislationService()
        service.register_adapter(PravoGovRuAdapter())
        sources = service.get_sources()
        assert len(sources) >= 1
        source = sources[0]
        assert isinstance(source, LegislationSource)
        assert source.id == "pravo.gov.ru"
        assert source.enabled is True

    @pytest.mark.asyncio
    async def test_search_unknown_source_fallback(self):
        """Searching with unknown source_id should fall back to first adapter."""
        service = LegislationService()
        adapter = PravoGovRuAdapter()
        service.register_adapter(adapter)

        # Unknown source ID — should fall back to the first adapter
        results, used_source, cached = await service.search(
            query="тестовый запрос",
            source_id="nonexistent",
        )
        assert used_source == "pravo.gov.ru" or used_source == ""
        assert isinstance(results, list)


# ─── PravoGovRuAdapter Unit Tests ──────────────────────────────────

class TestPravoGovRuAdapter:
    """Unit tests for the PravoGovRuAdapter."""

    def test_source_info(self):
        adapter = PravoGovRuAdapter()
        info = adapter.source_info()
        assert info.id == "pravo.gov.ru"
        assert info.enabled is True
        assert "правовой информации" in info.name

    @pytest.mark.asyncio
    async def test_search_timeout_graceful(self):
        """Should gracefully handle timeouts."""
        adapter = PravoGovRuAdapter(timeout=0.001)  # Very short timeout
        results = await adapter.search("тестовый запрос")
        assert isinstance(results, list)  # Should return empty list, not crash


# ─── API Integration Tests ─────────────────────────────────────────

class TestLegislationAPI:
    """Tests for GET /api/v1/legislation/* endpoints."""

    @pytest.mark.asyncio
    async def test_list_sources(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """GET /api/v1/legislation/sources should return source list."""
        response = await client.get(
            "/api/v1/legislation/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert len(data["sources"]) >= 1
        assert data["sources"][0]["id"] == "pravo.gov.ru"

    @pytest.mark.asyncio
    async def test_search_requires_auth(self, client: AsyncClient):
        """Search without auth should return 401."""
        response = await client.get(
            "/api/v1/legislation/search?query=test",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_search_min_length_validation(
        self, client: AsyncClient, admin_token: str
    ):
        """Query shorter than 2 chars should return 422."""
        response = await client.get(
            "/api/v1/legislation/search?query=x",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Happy path: search returns results structure."""
        response = await client.get(
            "/api/v1/legislation/search?query=налог&max_results=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # This may succeed or gracefully return empty — but should not crash
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "query" in data
            assert "source" in data
            assert "results" in data
            assert "total" in data
            assert "cached" in data
