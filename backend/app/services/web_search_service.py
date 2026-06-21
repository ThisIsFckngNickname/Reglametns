"""
Web search service for retrieving topic information from the internet.

Supports DuckDuckGo (free, no API key) as the default provider.
Can be extended to support Tavily, SerpAPI, etc.
"""

import logging
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for searching the internet for topic information."""

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the web for information on a topic.

        Args:
            query: Search query.
            max_results: Maximum number of results to return.

        Returns:
            List of dicts with 'title', 'snippet', 'url'.
        """
        if not settings.web_search_enabled:
            logger.info("Web search is disabled in settings")
            return []

        provider = settings.web_search_provider

        if provider == "duckduckgo":
            return await self._search_duckduckgo(query, max_results)
        elif provider == "tavily":
            return await self._search_tavily(query, max_results)
        elif provider == "serpapi":
            return await self._search_serpapi(query, max_results)
        else:
            logger.warning(f"Unknown web search provider: {provider}")
            return []

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search using DuckDuckGo (free, no API key)."""
        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    if i >= max_results:
                        break
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", r.get("snippet", "")),
                        "url": r.get("href", r.get("url", "")),
                    })

            logger.info(f"DuckDuckGo returned {len(results)} results for: {query[:50]}")
            return results

        except ImportError:
            logger.error(
                "DuckDuckGo search requires 'duckduckgo_search' package. "
                "Install with: pip install duckduckgo_search"
            )
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []

    async def _search_tavily(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search using Tavily API (requires API key)."""
        if not settings.tavily_api_key:
            logger.warning("Tavily API key not configured")
            return []

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for r in data.get("results", []):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("content", r.get("snippet", "")),
                        "url": r.get("url", ""),
                    })

                return results

        except ImportError:
            logger.error("Tavily search requires httpx package")
            return []
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    async def _search_serpapi(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search using SerpAPI (requires API key)."""
        if not settings.serpapi_api_key:
            logger.warning("SerpAPI API key not configured")
            return []

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": settings.serpapi_api_key,
                        "num": max_results,
                        "hl": "ru",
                        "gl": "ru",
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for r in data.get("organic_results", []):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "url": r.get("link", r.get("url", "")),
                    })

                return results

        except ImportError:
            logger.error("SerpAPI search requires httpx package")
            return []
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []


# Singleton
web_search_service = WebSearchService()
