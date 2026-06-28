"""
Web search service for retrieving topic information from the internet.

Supports DuckDuckGo (free, no API key) as the default provider.
Can be extended to support Tavily, SerpAPI, etc.

V2 (B1): Added enrich_prompt() method with page content extraction.
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

    # ── V2 (B1) methods ──────────────────────────────────────────────

    async def _fetch_page_content(self, url: str, timeout: int = 10) -> str | None:
        """Fetch and extract text content from a webpage.

        Uses httpx to fetch the page, then BeautifulSoup to extract
        readable text content.

        Args:
            url: Page URL to fetch.
            timeout: Request timeout in seconds.

        Returns:
            Extracted text content, or None if failed.
        """
        try:
            import httpx
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Remove non-content elements
                for tag in soup(["script", "style", "nav", "footer", "header",
                               "aside", "noscript", "iframe", "form"]):
                    tag.decompose()

                # Extract text
                text = soup.get_text(separator="\n", strip=True)

                # Clean up: collapse multiple newlines, limit length
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)

                # Limit to 5000 chars per page
                if len(text) > 5000:
                    text = text[:5000] + "\n\n[...]"

                return text

        except Exception as e:
            logger.warning(f"Failed to fetch page content {url}: {e}")
            return None

    async def enrich_prompt(self, topic: str, max_results: int = 5) -> str | None:
        """Search the web and format results for LLM prompt.

        Pipeline:
        1. Search DuckDuckGo for the topic
        2. Pick top 3 results
        3. Fetch full page content for each
        4. Format as structured text

        Args:
            topic: Document topic to search for.
            max_results: Max search results (default 5).

        Returns:
            Formatted text for prompt insertion, or None if search failed.
        """
        try:
            results = await self.search(topic, max_results)
            if not results:
                logger.info(f"No web search results for: {topic[:50]}")
                return None

            formatted = []
            for i, r in enumerate(results[:3], 1):
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("snippet", "")

                content = await self._fetch_page_content(url)

                formatted.append(f"Источник {i}: {title}")
                if content:
                    formatted.append(f"    {content[:1000]}")
                else:
                    formatted.append(f"    {snippet[:500]}")
                formatted.append(f"    URL: {url}")

            result_text = "\n".join(formatted)
            logger.info(
                f"Web search enrich_prompt: {len(results)} results, "
                f"{len(result_text)} chars for: {topic[:50]}"
            )
            return result_text

        except Exception as e:
            logger.error(f"Web search enrich_prompt failed: {e}", exc_info=True)
            return None  # Never block generation


# Singleton
web_search_service = WebSearchService()
