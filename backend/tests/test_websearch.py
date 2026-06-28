"""
Tests for WebSearchService enrich_prompt and _fetch_page_content methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.web_search_service import web_search_service


@pytest.mark.asyncio
async def test_enrich_prompt_empty_topic():
    """Empty topic should not raise an error."""
    result = await web_search_service.enrich_prompt("")
    # May return None or empty formatted string
    assert result is None or isinstance(result, str)


@pytest.mark.asyncio
async def test_enrich_prompt_handles_network_error():
    """Network error returns None, not raises."""
    with patch.object(web_search_service, "search", side_effect=Exception("No network")):
        result = await web_search_service.enrich_prompt("test topic")
        assert result is None


@pytest.mark.asyncio
async def test_enrich_prompt_search_no_results():
    """No search results should return None."""
    with patch.object(web_search_service, "search", return_value=[]):
        result = await web_search_service.enrich_prompt("test topic")
        assert result is None


@pytest.mark.asyncio
async def test_fetch_page_content_timeout():
    """Timeout should not raise."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Timeout")):
        content = await web_search_service._fetch_page_content("https://example.com")
        assert content is None


@pytest.mark.asyncio
async def test_fetch_page_content_returns_text():
    """Successful page fetch returns text."""
    mock_html = "<html><body><p>Test content</p></body></html>"
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        content = await web_search_service._fetch_page_content("https://example.com")
        assert content is not None
        assert "Test content" in content


@pytest.mark.asyncio
async def test_enrich_prompt_with_results():
    """enrich_prompt formats results correctly."""
    mock_results = [
        {"title": "Test Title 1", "snippet": "Test Snippet 1", "url": "https://example.com/1"},
        {"title": "Test Title 2", "snippet": "Test Snippet 2", "url": "https://example.com/2"},
    ]

    with patch.object(web_search_service, "search", return_value=mock_results):
        with patch.object(web_search_service, "_fetch_page_content", return_value="Full page content here"):
            result = await web_search_service.enrich_prompt("test topic")
            assert result is not None
            assert "Источник 1" in result
            assert "Test Title 1" in result
            assert "Источник 2" in result
            assert "Full page content here" in result


@pytest.mark.asyncio
async def test_enrich_prompt_fallback_to_snippet():
    """enrich_prompt falls back to snippet when page fetch fails."""
    mock_results = [
        {"title": "Test Title", "snippet": "Test Snippet", "url": "https://example.com"},
    ]

    with patch.object(web_search_service, "search", return_value=mock_results):
        with patch.object(web_search_service, "_fetch_page_content", return_value=None):
            result = await web_search_service.enrich_prompt("test topic")
            assert result is not None
            assert "Источник 1" in result
            assert "Test Title" in result
            assert "Test Snippet" in result
