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
    """Tests for /api/v1/legislation/* endpoints."""

    # ── Adapter sources (built-in) ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_adapter_sources(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """GET /api/v1/legislation/sources/adapters should return adapter list."""
        response = await client.get(
            "/api/v1/legislation/sources/adapters",
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
            assert "items" in data
            assert "total" in data
            assert "cached" in data

    # ── User-defined sources CRUD ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_user_sources(
        self, client: AsyncClient, admin_token: str
    ):
        """GET /api/v1/legislation/sources should return user-defined sources as array."""
        response = await client.get(
            "/api/v1/legislation/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # 3 seeded demo sources
        # First source should be Pravo.gov.ru
        assert data[0]["name"] == "Pravo.gov.ru"
        assert data[0]["source_type"] == "template_url"

    @pytest.mark.asyncio
    async def test_create_user_source(
        self, client: AsyncClient, admin_token: str
    ):
        """POST /api/v1/legislation/sources should create a new source."""
        payload = {
            "name": "Test Source",
            "source_type": "template_url",
            "url_template": "https://example.com/search?q={query}",
            "parser_type": "json",
            "selector": ".result",
        }
        response = await client.post(
            "/api/v1/legislation/sources",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Source"
        assert data["source_type"] == "template_url"
        assert data["url_template"] == "https://example.com/search?q={query}"
        assert data["id"] is not None
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_user_source_by_id(
        self, client: AsyncClient, admin_token: str
    ):
        """GET /api/v1/legislation/sources/:id should return the source."""
        # First list to get an ID
        list_resp = await client.get(
            "/api/v1/legislation/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        sources = list_resp.json()
        assert len(sources) > 0
        source_id = sources[0]["id"]

        response = await client.get(
            f"/api/v1/legislation/sources/{source_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == source_id
        assert data["name"] == sources[0]["name"]

    @pytest.mark.asyncio
    async def test_get_user_source_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """GET /api/v1/legislation/sources/:id with invalid id returns 404."""
        response = await client.get(
            "/api/v1/legislation/sources/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_user_source(
        self, client: AsyncClient, admin_token: str
    ):
        """PUT /api/v1/legislation/sources/:id should update fields."""
        # Create a source first
        create_resp = await client.post(
            "/api/v1/legislation/sources",
            json={"name": "Update Test", "source_type": "static_list"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        src = create_resp.json()
        source_id = src["id"]

        payload = {"name": "Updated Name", "description": "New description"}
        response = await client.put(
            f"/api/v1/legislation/sources/{source_id}",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"
        # Fields not sent should retain original values
        assert data["source_type"] == "static_list"

    @pytest.mark.asyncio
    async def test_update_user_source_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """PUT /api/v1/legislation/sources/:id with invalid id returns 404."""
        response = await client.put(
            "/api/v1/legislation/sources/99999",
            json={"name": "Nope"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_source(
        self, client: AsyncClient, admin_token: str
    ):
        """DELETE /api/v1/legislation/sources/:id should delete the source."""
        # Create a source first
        create_resp = await client.post(
            "/api/v1/legislation/sources",
            json={"name": "Delete Me", "source_type": "template_url"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        src = create_resp.json()
        source_id = src["id"]

        response = await client.delete(
            f"/api/v1/legislation/sources/{source_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_resp = await client.get(
            f"/api/v1/legislation/sources/{source_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_source_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """DELETE /api/v1/legislation/sources/:id with invalid id returns 404."""
        response = await client.delete(
            "/api/v1/legislation/sources/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_user_source(
        self, client: AsyncClient, admin_token: str
    ):
        """POST /api/v1/legislation/sources/:id/search should return mock results."""
        list_resp = await client.get(
            "/api/v1/legislation/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        sources = list_resp.json()
        assert len(sources) > 0
        source_id = sources[0]["id"]

        response = await client.post(
            f"/api/v1/legislation/sources/{source_id}/search",
            json={"query": "налог"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "title" in data[0]
        assert "url" in data[0]
        assert "snippet" in data[0]
        assert data[0]["source_name"] == sources[0]["name"]

    @pytest.mark.asyncio
    async def test_search_user_source_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """POST /api/v1/legislation/sources/:id/search with invalid id returns 404."""
        response = await client.post(
            "/api/v1/legislation/sources/99999/search",
            json={"query": "test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
