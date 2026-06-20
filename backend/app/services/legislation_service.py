"""
Legislation search service.

Provides a pluggable adapter interface for searching external legislation sources.
MVP ships with a built-in adapter for pravo.gov.ru (official Russian legal information portal).
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from bs4 import BeautifulSoup

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

    Uses the public search endpoint. Parses HTML responses with BeautifulSoup.
    """

    SEARCH_URL = "https://pravo.gov.ru/search/"
    BASE_URL = "https://pravo.gov.ru"

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[LegislationSearchResult]:
        """
        Search pravo.gov.ru for legal documents matching the query.
        """
        results: list[LegislationSearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                params: dict[str, str] = {
                    "q": query,
                    "page": "1",
                    "size": str(max_results),
                }
                resp = await client.get(self.SEARCH_URL, params=params)
                resp.raise_for_status()
                html = resp.text
                results = self._parse_results(html, query, max_results)
        except httpx.TimeoutException:
            logger.warning("pravo.gov.ru search timed out for query=%s", query)
        except httpx.HTTPStatusError as e:
            logger.warning("pravo.gov.ru returned status %s for query=%s", e.response.status_code, query)
        except Exception as e:
            logger.exception("Unexpected error searching pravo.gov.ru: %s", e)

        return results

    def _parse_results(
        self, html: str, query: str, max_results: int
    ) -> list[LegislationSearchResult]:
        """Parse the HTML search results page."""
        results: list[LegislationSearchResult] = []
        soup = BeautifulSoup(html, "lxml")

        # Look for result items — typically <div class="search-item"> or <li> elements
        for item in soup.select(".search-item, .result-item, .search-result-item, li.search-item"):
            if len(results) >= max_results:
                break

            title_el = item.select_one("a, .title, h3, h4")
            snippet_el = item.select_one(".snippet, .description, p, .text")

            title = title_el.get_text(strip=True) if title_el else None
            rel_url = title_el.get("href") if title_el and title_el.name == "a" else None
            snippet = snippet_el.get_text(strip=True) if snippet_el else None

            if not title:
                # Try <a> with text directly
                links = item.select("a")
                for a in links:
                    t = a.get_text(strip=True)
                    if t and len(t) > 5:
                        title = t
                        rel_url = a.get("href")
                        break

            if not title:
                continue

            url = None
            if rel_url:
                url = rel_url if rel_url.startswith("http") else f"{self.BASE_URL}{rel_url}"

            # Extract document number / date if present
            doc_number = None
            doc_date = None
            text_block = item.get_text(separator=" ", strip=True)
            if text_block:
                # Try to find patterns like № 123 or номер
                import re
                num_match = re.search(r"[Нн]омер[:\s]*(\S+)", text_block)
                if num_match:
                    doc_number = num_match.group(1)
                date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text_block)
                if date_match:
                    doc_date = date_match.group(1)

            results.append(LegislationSearchResult(
                title=title,
                url=url,
                snippet=snippet or text_block[:300] if text_block else None,
                document_number=doc_number,
                document_date=doc_date,
                source="pravo.gov.ru",
            ))

        # Fallback: if no structured results found, just return a placeholder
        if not results:
            logger.info("No structured results found on pravo.gov.ru for query=%s", query)

        return results

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
    """

    def __init__(self, ttl_seconds: int = 300):
        self._adapters: dict[str, LegislationAdapter] = {}
        self._cache = TTLCache(ttl_seconds=ttl_seconds)

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
