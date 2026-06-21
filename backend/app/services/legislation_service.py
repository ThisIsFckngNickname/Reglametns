"""
Legislation search service.

Provides a pluggable adapter interface for searching external legislation sources.
MVP ships with a built-in adapter for pravo.gov.ru (official Russian legal information portal).
Also manages user-defined sources via in-memory storage.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.schemas.legislation import (
    LegislationSearchResult,
    LegislationSource,
)

logger = logging.getLogger(__name__)


# ─── Simple In-Memory TTL Cache ─────────────────────────────────────

class TTLCache:
    """A minimal TTL cache for legislation search results."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, list[LegislationSearchResult]]] = {}

    def get(self, key: str) -> Optional[list[LegislationSearchResult]]:
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: list[LegislationSearchResult]) -> None:
        self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._data.clear()


# ─── Abstract Adapter ────────────────────────────────────────────────

class LegislationAdapter(ABC):
    """Abstract base for a legislation source adapter."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[LegislationSearchResult]:
        """Search the source for legislation matching the query."""
        ...

    @abstractmethod
    def source_info(self) -> LegislationSource:
        """Return metadata about this source."""
        ...


# ─── PravoGovRu Adapter ─────────────────────────────────────────────

class PravoGovRuAdapter(LegislationAdapter):
    """
    Adapter for pravo.gov.ru — official Russian legal information portal.

    Returns mock results for development/demo environments.
    No actual HTTP requests are made to pravo.gov.ru.
    """

    SEARCH_URL = "https://pravo.gov.ru/search/"
    BASE_URL = "https://pravo.gov.ru"

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[LegislationSearchResult]:
        """
        Search pravo.gov.ru — returns mock results for development/demo.
        """
        query_lower = query.lower() if query else ""

        mock_results = [
            LegislationSearchResult(
                title="Федеральный закон \"О персональных данных\"",
                url=f"http://pravo.gov.ru/proxy/ips/?search={query}",
                snippet="Настоящий Федеральный закон регулирует отношения, связанные с обработкой персональных данных...",
                document_number="152-ФЗ",
                document_date="2006-07-27",
                source="pravo.gov.ru",
            ),
            LegislationSearchResult(
                title="Федеральный закон \"Об информации, информационных технологиях и о защите информации\"",
                url=f"http://pravo.gov.ru/proxy/ips/?search={query}",
                snippet="Настоящий Федеральный закон регулирует отношения, возникающие при осуществлении права на поиск...",
                document_number="149-ФЗ",
                document_date="2006-07-27",
                source="pravo.gov.ru",
            ),
            LegislationSearchResult(
                title="Трудовой кодекс Российской Федерации",
                url=f"http://pravo.gov.ru/proxy/ips/?search={query}",
                snippet="Трудовой кодекс Российской Федерации регулирует трудовые отношения между работниками и работодателями...",
                document_number="197-ФЗ",
                document_date="2001-12-30",
                source="pravo.gov.ru",
            ),
            LegislationSearchResult(
                title="Федеральный закон \"Об акционерных обществах\"",
                url=f"http://pravo.gov.ru/proxy/ips/?search={query}",
                snippet="Настоящий Федеральный закон определяет порядок создания, реорганизации, ликвидации акционерных обществ...",
                document_number="208-ФЗ",
                document_date="1995-12-26",
                source="pravo.gov.ru",
            ),
            LegislationSearchResult(
                title="Федеральный закон \"О защите конкуренции\"",
                url=f"http://pravo.gov.ru/proxy/ips/?search={query}",
                snippet="Настоящий Федеральный закон определяет организационные и правовые основы защиты конкуренции...",
                document_number="135-ФЗ",
                document_date="2006-07-26",
                source="pravo.gov.ru",
            ),
        ]

        # Filter by query if provided
        if query_lower:
            filtered = [
                r for r in mock_results
                if query_lower in r.title.lower()
                or (r.document_number and query_lower in r.document_number.lower())
                or (r.snippet and query_lower in r.snippet.lower())
            ]
            return filtered[:max_results]

        return mock_results[:max_results]

    def source_info(self) -> LegislationSource:
        return LegislationSource(
            id="pravo.gov.ru",
            name="Официальный интернет-портал правовой информации",
            description="Официальные публикации законов, указов, постановлений РФ",
            base_url=self.SEARCH_URL,
            enabled=True,
        )


# ─── Legislation Service ────────────────────────────────────────────

class LegislationService:
    """
    Legislation search service that routes queries to registered adapters.
    Results are cached with a TTL.

    Also manages user-defined legislation sources via in-memory storage.
    """

    def __init__(self, ttl_seconds: int = 300):
        self._adapters: dict[str, LegislationAdapter] = {}
        self._cache = TTLCache(ttl_seconds=ttl_seconds)
        # ── In-memory user-defined sources ──
        self._next_source_id: int = 1
        now = datetime.now(timezone.utc).isoformat()
        self._user_sources: list[dict] = [
            {
                "id": self._next_id(),
                "holding_id": 0,
                "name": "Pravo.gov.ru",
                "source_type": "template_url",
                "url_template": "http://pravo.gov.ru/proxy/ips/?search={query}",
                "parser_type": "html",
                "selector": ".document-item",
                "is_active": True,
                "is_paid": False,
                "icon_url": None,
                "description": "Официальный портал правовой информации",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": self._next_id(),
                "holding_id": 0,
                "name": "Docs.cntd.ru",
                "source_type": "template_url",
                "url_template": "https://docs.cntd.ru/search?q={query}",
                "parser_type": "html",
                "selector": ".search-result-item",
                "is_active": True,
                "is_paid": False,
                "icon_url": None,
                "description": "Электронный фонд правовых и нормативно-технических документов",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": self._next_id(),
                "holding_id": 0,
                "name": "Консультант+",
                "source_type": "static_list",
                "url_template": None,
                "parser_type": None,
                "selector": None,
                "is_active": True,
                "is_paid": True,
                "icon_url": None,
                "description": "Справочно-правовая система КонсультантПлюс",
                "created_at": now,
                "updated_at": now,
            },
        ]

    def _next_id(self) -> int:
        nid = self._next_source_id
        self._next_source_id += 1
        return nid

    # ── User-defined source CRUD ────────────────────────────────────

    def get_user_sources(self) -> list[dict]:
        """Return all user-defined legislation sources."""
        return self._user_sources

    def get_user_source(self, source_id: int) -> dict | None:
        """Get a single user-defined source by id, or None."""
        for src in self._user_sources:
            if src["id"] == source_id:
                return src
        return None

    def create_user_source(self, data: dict) -> dict:
        """Create a new user-defined source with auto-id and timestamps."""
        now = datetime.now(timezone.utc).isoformat()
        source: dict = {
            "id": self._next_id(),
            "holding_id": data.get("holding_id", 0),
            "name": data["name"],
            "source_type": data.get("source_type", "template_url"),
            "url_template": data.get("url_template"),
            "parser_type": data.get("parser_type"),
            "selector": data.get("selector"),
            "is_active": data.get("is_active", True),
            "is_paid": data.get("is_paid", False),
            "icon_url": data.get("icon_url"),
            "description": data.get("description"),
            "created_at": now,
            "updated_at": now,
        }
        self._user_sources.append(source)
        return source

    def update_user_source(self, source_id: int, data: dict) -> dict | None:
        """Update fields of an existing source. Returns updated source or None."""
        for src in self._user_sources:
            if src["id"] == source_id:
                updatable = {
                    "name", "source_type", "url_template", "parser_type",
                    "selector", "is_active", "is_paid", "icon_url", "description",
                }
                for key, value in data.items():
                    if key in updatable:
                        src[key] = value
                src["updated_at"] = datetime.now(timezone.utc).isoformat()
                return src
        return None

    def delete_user_source(self, source_id: int) -> bool:
        """Delete a user-defined source by id. Returns True if deleted."""
        for i, src in enumerate(self._user_sources):
            if src["id"] == source_id:
                self._user_sources.pop(i)
                return True
        return False

    def search_user_source(self, source_id: int, query: str) -> list[dict]:
        """Return mock search results for a user-defined source."""
        # Simulated search results matching the MSW mock data style
        mock_results = [
            {
                "title": f"Федеральный закон от 13.06.2023 № 258-ФЗ",
                "url": f"http://pravo.gov.ru/proxy/ips/?search={query}",
                "snippet": "О внесении изменений в отдельные законодательные акты Российской Федерации...",
                "date": "13.06.2023",
                "source_name": "",
            },
            {
                "title": f"Постановление Правительства РФ от 15.03.2024 № 312",
                "url": f"http://pravo.gov.ru/proxy/ips/?search={query}",
                "snippet": "Об утверждении порядка предоставления субсидий...",
                "date": "15.03.2024",
                "source_name": "",
            },
            {
                "title": f"Приказ Минфина России от 01.02.2024 № 15н",
                "url": f"http://pravo.gov.ru/proxy/ips/?search={query}",
                "snippet": "Об утверждении форм налоговых деклараций...",
                "date": "01.02.2024",
                "source_name": "",
            },
        ]
        # Attach the source name for context
        source = self.get_user_source(source_id)
        source_name = source["name"] if source else ""
        for r in mock_results:
            r["source_name"] = source_name
        return mock_results

    def register_adapter(self, adapter: LegislationAdapter) -> None:
        """Register a legislation source adapter."""
        info = adapter.source_info()
        self._adapters[info.id] = adapter

    def get_sources(self) -> list[LegislationSource]:
        """Return metadata about all registered sources."""
        return [a.source_info() for a in self._adapters.values()]

    async def search(
        self,
        query: str,
        source_id: Optional[str] = None,
        max_results: int = 10,
    ) -> tuple[list[LegislationSearchResult], str, bool]:
        """
        Search legislation.

        Args:
            query: Search query string.
            source_id: Optional source ID to limit search. If None, searches all.
            max_results: Max results per source.

        Returns:
            Tuple of (results, source_id_used, was_cached).
        """
        if source_id and source_id not in self._adapters:
            logger.warning("Unknown source_id=%s, falling back to first available", source_id)
            source_id = None

        if source_id:
            adapters_to_search = [(source_id, self._adapters[source_id])]
        else:
            adapters_to_search = list(self._adapters.items())

        all_results: list[LegislationSearchResult] = []
        used_source = ""
        was_cached = False

        for sid, adapter in adapters_to_search:
            # Check cache
            cache_key = f"{sid}:{query}:{max_results}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                all_results.extend(cached)
                used_source = sid
                was_cached = True
                continue

            results = await adapter.search(query, max_results=max_results)
            self._cache.set(cache_key, results)
            all_results.extend(results)
            used_source = sid
            break  # Only search first adapter for now

        return all_results, used_source, was_cached


# ─── Singleton ──────────────────────────────────────────────────────

legislation_service = LegislationService()
legislation_service.register_adapter(PravoGovRuAdapter())
