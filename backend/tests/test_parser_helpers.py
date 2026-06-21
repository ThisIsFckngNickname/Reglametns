"""Tests for parser helpers."""
from app.parsers.helpers import (
    _extract_terms_from_text,
    _extract_abbreviations_from_text,
    _build_section_hierarchy,
    _table_to_html,
    _is_term_section,
    _is_abbreviation_section,
    _find_term_abbreviation_sections,
    ParseResult,
)


def test_extract_terms_em_dash():
    """Test term extraction with em dash."""
    text = "Регламент — нормативный документ"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 1
    assert terms[0]["term"] == "Регламент"
    assert terms[0]["definition"] == "нормативный документ"


def test_extract_terms_en_dash():
    """Test term extraction with en dash."""
    text = "Процесс – последовательность действий"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 1
    assert terms[0]["term"] == "Процесс"


def test_extract_terms_colon():
    """Test term extraction with colon."""
    text = "Документ: официальная бумага"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 1
    assert terms[0]["term"] == "Документ"


def test_extract_terms_tab():
    """Test term extraction with tab separator."""
    text = "Акт\tдокумент, составленный комиссией"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 1
    assert terms[0]["term"] == "Акт"


def test_extract_terms_multiple_lines():
    """Test term extraction from multiple lines."""
    text = "Регламент — нормативный документ\nПротокол – документ собрания"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 2


def test_extract_terms_skips_numeric():
    """Test that numeric prefixes are skipped."""
    text = "1. Пункт — описание"
    terms = _extract_terms_from_text(text)
    assert len(terms) == 0


def test_extract_terms_empty():
    """Test empty text returns empty list."""
    assert _extract_terms_from_text("") == []
    assert _extract_terms_from_text("   \n  \n") == []


def test_extract_abbreviations():
    """Test abbreviation extraction with em dash."""
    text = "ООО — Общество с ограниченной ответственностью"
    abbrs = _extract_abbreviations_from_text(text)
    assert len(abbrs) == 1
    assert abbrs[0]["abbreviation"] == "ООО"
    assert abbrs[0]["full_form"] == "Общество с ограниченной ответственностью"


def test_extract_abbreviations_paren():
    """Test abbreviation extraction with parentheses."""
    text = "ООО (Общество с ограниченной ответственностью)"
    abbrs = _extract_abbreviations_from_text(text)
    assert len(abbrs) == 1
    assert abbrs[0]["abbreviation"] == "ООО"


def test_extract_abbreviations_cyrillic():
    """Test abbreviation extraction with Cyrillic uppercase."""
    text = "ФЗ — Федеральный закон"
    abbrs = _extract_abbreviations_from_text(text)
    assert len(abbrs) == 1
    assert abbrs[0]["abbreviation"] == "ФЗ"


def test_extract_abbreviations_empty():
    """Test empty text returns empty list."""
    assert _extract_abbreviations_from_text("") == []


def test_build_section_hierarchy():
    """Test section hierarchy building."""
    sections = [
        {"title": "1", "level": 1, "order_num": 1},
        {"title": "1.1", "level": 2, "order_num": 2},
        {"title": "2", "level": 1, "order_num": 3},
    ]
    result = _build_section_hierarchy(sections)
    assert result[0]["parent_id"] is None
    assert result[1]["parent_id"] == 1  # parent is first section
    assert result[2]["parent_id"] is None


def test_build_section_hierarchy_nested():
    """Test deeper nesting."""
    sections = [
        {"title": "1", "level": 1, "order_num": 1},
        {"title": "1.1", "level": 2, "order_num": 2},
        {"title": "1.1.1", "level": 3, "order_num": 3},
        {"title": "1.2", "level": 2, "order_num": 4},
    ]
    result = _build_section_hierarchy(sections)
    assert result[0]["parent_id"] is None
    assert result[1]["parent_id"] == 1
    assert result[2]["parent_id"] == 2
    assert result[3]["parent_id"] == 1


def test_build_section_hierarchy_empty():
    """Test empty input."""
    assert _build_section_hierarchy([]) == []


def test_table_to_html():
    """Test HTML table generation."""
    html = _table_to_html(["A", "B"], [["1", "2"]], "Test")
    assert "<caption>Test</caption>" in html
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html
    assert "<table" in html
    assert "</table>" in html


def test_table_to_html_no_caption():
    """Test HTML table without caption."""
    html = _table_to_html(["A"], [["1"]])
    assert "<caption>" not in html
    assert "<th>A</th>" in html


def test_table_to_html_no_headers():
    """Test HTML table without headers."""
    html = _table_to_html([], [["1", "2"]])
    assert "<thead>" not in html


def test_table_to_html_empty():
    """Test empty table returns basic HTML."""
    html = _table_to_html([], [])
    assert "<table" in html
    assert "</table>" in html


def test_is_term_section():
    """Test term section detection."""
    assert _is_term_section("Термины и определения")
    assert _is_term_section("Основные понятия")
    assert _is_term_section("Глоссарий")
    assert _is_term_section("Определение")
    assert not _is_term_section("Общие положения")
    assert not _is_term_section("Общие определения")  # 'определения' ≠ 'определение'
    assert not _is_term_section("")


def test_is_abbreviation_section():
    """Test abbreviation section detection."""
    assert _is_abbreviation_section("Список сокращений")
    assert _is_abbreviation_section("Принятые сокращения")
    assert _is_abbreviation_section("Условное обозначение")
    assert _is_abbreviation_section("Сокращение")
    assert not _is_abbreviation_section("Введение")
    assert not _is_abbreviation_section("")


def test_find_term_abbreviation_sections():
    """Test finding term/abbreviation sections."""
    sections = [
        {"title": "Термины и определения", "order_num": 2},
            {"title": "Список сокращений", "order_num": 3},
        {"title": "Введение", "order_num": 1},
    ]
    term_ids, abbr_ids = _find_term_abbreviation_sections(sections)
    assert 2 in term_ids
    assert 3 in abbr_ids
    assert 1 not in term_ids
    assert 1 not in abbr_ids


def test_find_term_abbreviation_sections_empty():
    """Test empty sections."""
    term_ids, abbr_ids = _find_term_abbreviation_sections([])
    assert term_ids == set()
    assert abbr_ids == set()


def test_parse_result_defaults():
    """Test ParseResult defaults."""
    result = ParseResult()
    assert result.sections == []
    assert result.tables == []
    assert result.terms == []
    assert result.abbreviations == []
    assert result.lists == []


def test_parse_result_with_data():
    """Test ParseResult with data."""
    result = ParseResult(
        sections=[{"title": "Test"}],
        terms=[{"term": "Test", "definition": "Desc"}],
    )
    assert len(result.sections) == 1
    assert len(result.terms) == 1
    assert result.tables == []
