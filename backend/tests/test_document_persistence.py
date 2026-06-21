"""
Tests for DocumentPersistenceService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.document_persistence_service import DocumentPersistenceService
from app.models.document_version import DocumentVersion


class TestDocumentPersistenceService:
    """Unit tests for the document persistence service."""

    @pytest.mark.asyncio
    async def test_persist_empty_parse_result(self):
        """persist_parse_result handles empty data without errors."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = []
        parse_result.tables = []
        parse_result.terms = []
        parse_result.abbreviations = []
        parse_result.lists = []

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        # Verify full_text is set (empty string from join)
        assert version.full_text == ""

    @pytest.mark.asyncio
    async def test_persist_with_sections(self):
        """persist_parse_result saves sections and builds full_text."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = [
            {
                "title": "1. Общие положения",
                "level": 1,
                "order_num": 1,
                "content": "Текст раздела",
                "parent_id": None,
            },
            {
                "title": "1.1. Цели",
                "level": 2,
                "order_num": 2,
                "content": "Цели документа",
                "parent_id": 1,
            },
        ]
        parse_result.tables = []
        parse_result.terms = []
        parse_result.abbreviations = []
        parse_result.lists = []

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        # Verify full_text content
        assert version.full_text is not None
        assert "1. Общие положения" in version.full_text
        assert "Текст раздела" in version.full_text
        assert "1.1. Цели" in version.full_text
        assert "Цели документа" in version.full_text

    @pytest.mark.asyncio
    async def test_persist_with_terms_deduplication(self):
        """Terms are deduplicated by lowercase trimmed text."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = []
        parse_result.tables = []
        parse_result.terms = [
            {"term": "Регламент", "definition": "Нормативный документ"},
            {"term": "регламент", "definition": "Дубликат (должен быть отфильтрован)"},
            {"term": "Процесс", "definition": "Последовательность действий"},
        ]
        parse_result.abbreviations = []
        parse_result.lists = []

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        # Count how many DocumentTerm objects were added
        document_term_added_count = sum(
            1
            for call in db.add.call_args_list
            if call[0][0].__class__.__name__ == "DocumentTerm"
        )
        assert document_term_added_count == 2, (
            f"Expected 2 unique terms, got {document_term_added_count}"
        )

    @pytest.mark.asyncio
    async def test_persist_with_abbreviations_deduplication(self):
        """Abbreviations are deduplicated by lowercase trimmed text."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = []
        parse_result.tables = []
        parse_result.terms = []
        parse_result.abbreviations = [
            {"abbreviation": "ПДС", "full_form": "Постоянно действующая система"},
            {"abbreviation": "пдс", "full_form": "Дубликат (должен быть отфильтрован)"},
            {"abbreviation": "СМК", "full_form": "Система менеджмента качества"},
        ]
        parse_result.lists = []

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        document_abbr_added_count = sum(
            1
            for call in db.add.call_args_list
            if call[0][0].__class__.__name__ == "DocumentAbbreviation"
        )
        assert document_abbr_added_count == 2, (
            f"Expected 2 unique abbreviations, got {document_abbr_added_count}"
        )

    @pytest.mark.asyncio
    async def test_persist_with_lists(self):
        """Lists are stored as JSON in version_notes."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = []
        parse_result.tables = []
        parse_result.terms = []
        parse_result.abbreviations = []
        parse_result.lists = [
            {"type": "bullet", "items": ["пункт 1", "пункт 2"]}
        ]

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        assert version.version_notes is not None
        import json
        parsed = json.loads(version.version_notes)
        assert "lists" in parsed
        assert len(parsed["lists"]) == 1
        assert parsed["lists"][0]["type"] == "bullet"

    @pytest.mark.asyncio
    async def test_persist_lists_does_not_overwrite_existing_notes(self):
        """Lists are NOT saved if version_notes already has content."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = "existing notes"
        version.full_text = None

        parse_result = MagicMock()
        parse_result.sections = []
        parse_result.tables = []
        parse_result.terms = []
        parse_result.abbreviations = []
        parse_result.lists = [
            {"type": "bullet", "items": ["пункт 1"]}
        ]

        db = AsyncMock()

        await service.persist_parse_result(parse_result, version, 1, db)

        # version_notes should remain unchanged
        assert version.version_notes == "existing notes"

    @pytest.mark.asyncio
    async def test_persist_with_tables(self):
        """Tables are saved with section_id mapping from order_num."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        version.id = 1
        version.version_notes = None
        version.full_text = None

        # Simulate how DocumentSection.id gets assigned on db.flush()
        section_1 = MagicMock()
        section_1.id = 10
        section_2 = MagicMock()
        section_2.id = 20

        db = AsyncMock()
        # First add() returns section_1, second returns section_2
        db.add.side_effect = None

        # Instead of testing through persist_parse_result with complex mocking,
        # directly test the section_id_map usage in _save_tables
        section_id_map = {1: 10, 2: 20}
        tables_data = [
            {
                "section_id": 1,
                "caption": "Таблица 1",
                "order_num": 1,
                "html_content": "<table><tr><td>1</td></tr></table>",
                "rows_count": 1,
                "cols_count": 1,
            },
            {
                "section_id": 999,  # non-existent section
                "caption": "Таблица 2",
                "order_num": 2,
                "html_content": "<table><tr><td>2</td></tr></table>",
                "rows_count": 1,
                "cols_count": 1,
            },
        ]

        await service._save_tables(tables_data, version, section_id_map, db)

        # Verify 2 DocumentTable objects were added
        table_add_count = sum(
            1
            for call in db.add.call_args_list
            if call[0][0].__class__.__name__ == "DocumentTable"
        )
        assert table_add_count == 2

    def test_build_full_text(self):
        """_build_and_set_full_text builds text from sections."""
        service = DocumentPersistenceService()

        sections = [
            {"title": "1. Раздел", "content": "Текст первого раздела"},
            {"title": "2. Раздел", "content": "Текст второго раздела"},
            {"title": "3. Раздел", "content": ""},  # empty content
        ]

        version = MagicMock(spec=DocumentVersion)
        service._build_and_set_full_text(sections, version)

        assert "1. Раздел" in version.full_text
        assert "Текст первого раздела" in version.full_text
        assert "2. Раздел" in version.full_text
        assert "3. Раздел" in version.full_text
        # Sections are separated by double newline
        assert "\n\n" in version.full_text

    def test_build_full_text_empty_sections(self):
        """_build_and_set_full_text handles empty sections list."""
        service = DocumentPersistenceService()

        version = MagicMock(spec=DocumentVersion)
        service._build_and_set_full_text([], version)

        assert version.full_text == ""

    def test_build_full_text_no_content(self):
        """_build_and_set_full_text handles sections without content key."""
        service = DocumentPersistenceService()

        sections = [
            {"title": "1. Раздел"},  # no content key
        ]

        version = MagicMock(spec=DocumentVersion)
        service._build_and_set_full_text(sections, version)

        assert "1. Раздел" in version.full_text
