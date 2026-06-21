"""
Tests for generator sub-service components.

Covers:
- ResponseHandler: parse_response, format_style_patterns_for_prompt, get_output_path, get_mock_response
- TextExtractor: extract_draft_text with no files, txt files
- DataLoader: interface smoke test
"""

import json
import os
import tempfile
from io import BytesIO

import pytest
from fastapi import UploadFile as FastAPIUploadFile

from app.services.generators.response_handler import response_handler
from app.services.generators.text_extractor import text_extractor
from app.services.generators.data_loader import data_loader
from app.services.generators.response_handler import MOCK_RESPONSE


class TestResponseHandler:
    """Tests for ResponseHandler."""

    @pytest.mark.asyncio
    async def test_parse_response_valid_json(self):
        """Test parsing valid JSON."""
        result = await response_handler.parse_response('{"title": "Test"}')
        assert result["title"] == "Test"

    @pytest.mark.asyncio
    async def test_parse_response_markdown_block(self):
        """Test parsing JSON from markdown code block."""
        raw = 'Some text\n```json\n{"title": "From Block"}\n```\nMore text'
        result = await response_handler.parse_response(raw)
        assert result["title"] == "From Block"

    @pytest.mark.asyncio
    async def test_parse_response_bare_braces(self):
        """Test parsing JSON from bare braces (strategy 3)."""
        raw = "Here is the data: {\"title\": \"Bare\", \"count\": 42}"
        result = await response_handler.parse_response(raw)
        assert result["title"] == "Bare"
        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_parse_response_empty(self):
        """Test parsing empty response returns mock."""
        result = await response_handler.parse_response("")
        assert result["title"] == MOCK_RESPONSE["title"]

    @pytest.mark.asyncio
    async def test_parse_response_none(self):
        """Test parsing None returns mock."""
        result = await response_handler.parse_response(None)  # type: ignore[arg-type]
        assert result["title"] == MOCK_RESPONSE["title"]

    @pytest.mark.asyncio
    async def test_parse_response_invalid(self):
        """Test parsing invalid JSON raises error."""
        from app.core.exceptions import BadRequestException

        with pytest.raises(BadRequestException):
            await response_handler.parse_response("Not JSON at all {{{")

    def test_format_style_patterns_empty(self):
        """Test empty style settings."""
        assert response_handler.format_style_patterns_for_prompt(None) == ""
        assert response_handler.format_style_patterns_for_prompt({}) == ""

    def test_format_style_patterns_with_data(self):
        """Test style patterns with data."""
        settings = {
            "typical_phrases": ["Фраза 1", "Фраза 2"],
            "avg_sentence_length": 15,
        }
        result = response_handler.format_style_patterns_for_prompt(settings)
        assert "Фраза 1" in result
        assert "15" in result

    def test_format_style_patterns_no_phrases(self):
        """Test style patterns with avg length only."""
        settings = {"avg_sentence_length": 10.5}
        result = response_handler.format_style_patterns_for_prompt(settings)
        assert "10.5" in result

    def test_get_output_path(self):
        """Test output path generation."""
        path = response_handler.get_output_path(1, "Test Document")
        assert path.endswith(".docx")
        assert "1" in path
        assert "Test_Document" in path

    def test_get_output_path_special_chars(self):
        """Test output path with special characters in title."""
        path = response_handler.get_output_path(2, "Регламент: <Закупки> & ")
        assert path.endswith(".docx")
        assert "2" in path

    def test_get_mock_response(self):
        """Test mock response data."""
        mock = response_handler.get_mock_response()
        assert "title" in mock
        assert "sections" in mock
        assert "terms" in mock
        assert "abbreviations" in mock
        # Should be a copy, not the same dict
        assert mock is not MOCK_RESPONSE


class TestTextExtractor:
    """Tests for TextExtractor."""

    @pytest.mark.asyncio
    async def test_extract_draft_text_no_files(self):
        """Test with no files."""
        result = await text_extractor.extract_draft_text(None)
        assert result == ""
        result = await text_extractor.extract_draft_text([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_draft_text_txt(self):
        """Test extracting text from a .txt file."""
        content = b"Line 1\nLine 2\nLine 3"
        file = FastAPIUploadFile(
            filename="test.txt",
            file=BytesIO(content),
        )
        result = await text_extractor.extract_draft_text([file])
        assert "Line 1" in result
        assert "test.txt" in result

    @pytest.mark.asyncio
    async def test_extract_draft_text_multiple(self):
        """Test extracting text from multiple files."""
        file1 = FastAPIUploadFile(
            filename="a.txt",
            file=BytesIO(b"Content A"),
        )
        file2 = FastAPIUploadFile(
            filename="b.txt",
            file=BytesIO(b"Content B"),
        )
        result = await text_extractor.extract_draft_text([file1, file2])
        assert "Content A" in result
        assert "Content B" in result
        assert "a.txt" in result
        assert "b.txt" in result


class TestDataLoader:
    """Smoke tests for DataLoader interface."""

    def test_singleton_exists(self):
        """DataLoader singleton should be importable."""
        assert data_loader is not None
        assert hasattr(data_loader, "load_company")
        assert hasattr(data_loader, "load_influencing_documents")
        assert hasattr(data_loader, "load_company_terms")
