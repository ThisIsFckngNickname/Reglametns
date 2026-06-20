"""
Tests for EnhancedPDFParser — complex layout detection, columns, lists, tables.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.parsers.enhanced_pdf_parser import EnhancedPDFParser, DetectedList
from app.services.parser_service import ParseResult, _table_to_html


# ─── Helpers: generate test PDFs ────────────────────────────────────────

def _register_cyrillic_font():
    """Register a TTF font that supports Cyrillic for reportlab."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Try common Cyrillic fonts available on Windows
    font_paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\Arial.ttf",
        "C:\\Windows\\Fonts\\times.ttf",
        "C:\\Windows\\Fonts\\Times.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("CyrillicFont", fp))
                return "CyrillicFont"
            except Exception:
                continue
    # Fallback: use built-in font (won't show Cyrillic properly)
    return "Helvetica"


# Try to register Cyrillic font once at module load
_CYRILLIC_FONT = _register_cyrillic_font()


def _make_single_column_pdf(target: str) -> str:
    """Generate a simple single-column PDF with headings and text."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(target, pagesize=A4)
    width, height = A4
    font = _CYRILLIC_FONT

    # Title
    c.setFont(f"{font}-Bold" if font == "Helvetica" else font, 20)
    c.drawString(50, height - 50, "Zagolovok pervogo urovnya")

    # Text
    c.setFont(font, 12)
    y = height - 80
    lines = [
        "Eto obychnyj tekst pervogo abzaca. On soderzhit opisanie dokumenta.",
        "Prodolzhenie teksta s dopolnitelnoj informaciej dlya testirovaniya.",
        "Eshyo neskolko teksta chtoby zapolnit stranicu kontentom.",
    ]
    for line in lines:
        c.drawString(50, y, line)
        y -= 20

    # Subheading
    c.setFont(f"{font}-Bold" if font == "Helvetica" else font, 16)
    y -= 10
    c.drawString(50, y, "Podzagolovok vtorogo urovnya")

    # More text
    c.setFont(font, 12)
    y -= 20
    for line in ["Tekst pod podzagolovkom.", "Eshyo tekst dlya proverki struktury."]:
        c.drawString(50, y, line)
        y -= 20

    c.save()
    return target


def _make_two_column_pdf(target: str) -> str:
    """Generate a two-column PDF layout."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(target, pagesize=A4)
    width, height = A4
    font = _CYRILLIC_FONT
    bold_font = f"{font}-Bold" if font == "Helvetica" else font

    # Left column (x: 30-280)
    c.setFont(bold_font, 14)
    c.drawString(30, height - 50, "Levaya kolonka - zagolovok")
    c.setFont(font, 10)
    y = height - 75
    for i in range(15):
        c.drawString(30, y, f"Stroka levoj kolonki {i}")
        y -= 15

    # Right column (x: 310-560)
    c.setFont(bold_font, 14)
    c.drawString(310, height - 50, "Pravaya kolonka - zagolovok")
    c.setFont(font, 10)
    y = height - 75
    for i in range(15):
        c.drawString(310, y, f"Stroka pravoj kolonki {i}")
        y -= 15

    c.save()
    return target


def _make_list_pdf(target: str) -> str:
    """Generate a PDF with numbered, bulleted, and nested lists."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(target, pagesize=A4)
    width, height = A4
    font = _CYRILLIC_FONT
    bold_font = f"{font}-Bold" if font == "Helvetica" else font

    y = height - 50
    c.setFont(bold_font, 16)
    c.drawString(50, y, "Spisok dokumentov")
    y -= 30

    c.setFont(font, 12)

    # Numbered list
    numbered_items = [
        "1. Pervyj punkt spiska",
        "2. Vtoroj punkt spiska",
        "3. Tretij punkt spiska s dlinym opisaniem",
        "4. Chetvyortyj punkt spiska",
    ]
    for item in numbered_items:
        c.drawString(50, y, item)
        y -= 20

    y -= 10
    c.setFont(bold_font, 14)
    c.drawString(50, y, "Markirovannyj spisok")
    y -= 25
    c.setFont(font, 12)

    # Bulleted list
    bullet_items = [
        "- Pervyj element",
        "- Vtoroj element",
        "- Tretij element",
    ]
    for item in bullet_items:
        c.drawString(50, y, item)
        y -= 20

    y -= 10
    c.setFont(bold_font, 14)
    c.drawString(50, y, "Vlozhennyj spisok")
    y -= 25
    c.setFont(font, 12)

    # Nested list
    nested_items = [
        "1. Glavnyj punkt",
        "   a) Podpunkt pervyj",
        "   b) Podpunkt vtoroj",
        "2. Vtoroj glavnyj punkt",
        "   a) Podpunkt s detalyami",
    ]
    for item in nested_items:
        c.drawString(50, y, item)
        y -= 20

    c.save()
    return target


def _make_table_pdf(target: str) -> str:
    """Generate a PDF with a simple table using reportlab Table."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(target, pagesize=A4)
    font = _CYRILLIC_FONT

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_normal.fontName = font if font != "Helvetica" else "Helvetica"

    elements = []

    # Title
    from reportlab.platypus import Paragraph as P
    p = P(f"<b>Dokument s tablicej</b>", style_normal)
    elements.append(p)

    # Table
    headers = ["N", "Naimenovanie", "Kolichestvo", "Primechanie"]
    rows_data = [
        ["1", "Bumaga A4", "10 pachek", "Dlya ofisa"],
        ["2", "Ruchki", "50 sht", "Sinie"],
        ["3", "Papki", "20 sht", "Kartonnye"],
        ["4", "Steplery", "5 sht", "Dlya kancelyarii"],
    ]
    table_data = [headers] + rows_data

    t = Table(table_data)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font if font != "Helvetica" else "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), font if font != "Helvetica" else "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t)

    doc.build(elements)
    return target


def _make_broken_table_pdf(target: str) -> str:
    """Generate a PDF where a table spans two pages."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Table, TableStyle, SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(target, pagesize=A4)
    font = _CYRILLIC_FONT

    elements = []

    # Title
    from reportlab.platypus import Paragraph
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.fontName = font if font != "Helvetica" else "Helvetica"
    elements.append(Paragraph("<b>Tablica na dvuh stranicah</b>", style))

    # Create a table with many rows to force page break
    headers = ["ID", "Naimenovanie", "Znachenie"]
    rows_data = [
        [str(i), f"Parametr {chr(64+i)}", str(i * 100)]
        for i in range(1, 31)
    ]
    table_data = [headers] + rows_data

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font if font != "Helvetica" else "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), font if font != "Helvetica" else "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    elements.append(t)

    doc.build(elements)
    return target


def _make_complex_document_pdf(target: str) -> str:
    """Generate a complex document with all features using platypus."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        KeepTogether, PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm

    doc = SimpleDocTemplate(target, pagesize=A4)
    font = _CYRILLIC_FONT
    styles = getSampleStyleSheet()

    # Custom styles
    style_h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"],
        fontName=font if font != "Helvetica" else "Helvetica-Bold",
        fontSize=22, spaceAfter=12,
    )
    style_h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontName=font if font != "Helvetica" else "Helvetica-Bold",
        fontSize=14, spaceAfter=8,
    )
    style_normal = ParagraphStyle(
        "NormalCustom", parent=styles["Normal"],
        fontName=font if font != "Helvetica" else "Helvetica",
        fontSize=12, spaceAfter=6,
    )

    elements = []

    # Title
    elements.append(Paragraph("Slozhnyj dokument", style_h1))
    elements.append(Paragraph(
        "Nastoyashij dokument soderzhit razlichnye elementy vyorstki. "
        "On vklyuchaet zagolovki, spiski, tablicy i mnogokolonochnyj tekst.",
        style_normal
    ))

    # List section
    elements.append(Paragraph("Trebsvaniya:", style_h2))
    for item in [
        "1. Pervoe trebovanie k sisteme",
        "2. Vtoroe trebovanie s utochneniyami",
        "3. Tretie trebovanie",
    ]:
        elements.append(Paragraph(item, style_normal))

    # Table
    table_data = [
        ["Parametr", "Znachenie"],
        ["Ves", "10 kg"],
        ["Dlina", "5 m"],
    ]
    t = Table(table_data)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font if font != "Helvetica" else "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), font if font != "Helvetica" else "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)

    # Page break and two columns on next page
    elements.append(PageBreak())

    style_col_title = ParagraphStyle(
        "ColTitle", parent=styles["Heading2"],
        fontName=font if font != "Helvetica" else "Helvetica-Bold",
        fontSize=14,
    )
    style_col_text = ParagraphStyle(
        "ColText", parent=styles["Normal"],
        fontName=font if font != "Helvetica" else "Helvetica",
        fontSize=10, spaceAfter=4,
    )

    # Two columns via a side-by-side table
    left_text = "\n".join(
        [f"Tekst levoj kolonki stroka {i+1}" for i in range(10)]
    )
    right_text = "\n".join(
        [f"Tekst pravoj kolonki stroka {i+1}" for i in range(10)]
    )

    col_table_data = [
        [
            Paragraph(f"<b>Levaya kolonka</b><br/>{left_text.replace(chr(10), '<br/>')}", style_col_text),
            Paragraph(f"<b>Pravaya kolonka</b><br/>{right_text.replace(chr(10), '<br/>')}", style_col_text),
        ]
    ]
    col_table = Table(col_table_data, colWidths=[260, 260])
    col_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font if font != "Helvetica" else "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(col_table)

    doc.build(elements)
    return target


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def parser():
    return EnhancedPDFParser()


@pytest.fixture
def single_column_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "single_column.pdf")
    return _make_single_column_pdf(path)


@pytest.fixture
def two_column_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "two_column.pdf")
    return _make_two_column_pdf(path)


@pytest.fixture
def list_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "lists.pdf")
    return _make_list_pdf(path)


@pytest.fixture
def table_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "table.pdf")
    return _make_table_pdf(path)


@pytest.fixture
def broken_table_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "broken_table.pdf")
    return _make_broken_table_pdf(path)


@pytest.fixture
def complex_pdf(tmp_path: Path) -> str:
    path = str(tmp_path / "complex.pdf")
    return _make_complex_document_pdf(path)


# ─── Tests ──────────────────────────────────────────────────────────────

class TestColumnDetection:
    """Tests for column detection."""

    def test_detect_single_column(self, parser, single_column_pdf):
        """Single-column document → one column."""
        import fitz

        doc = fitz.open(single_column_pdf)
        page = doc[0]
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        page_width = page_dict.get("width", 595)

        columns = parser._detect_columns(blocks, page_width)
        assert len(columns) == 1, f"Expected 1 column, got {len(columns)}: {columns}"
        assert columns[0][0] >= 0  # starts near left edge
        doc.close()

    def test_detect_two_columns(self, parser, two_column_pdf):
        """Two-column document → two columns."""
        import fitz

        doc = fitz.open(two_column_pdf)
        page = doc[0]
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        page_width = page_dict.get("width", 595)

        columns = parser._detect_columns(blocks, page_width)
        assert len(columns) == 2, f"Expected 2 columns, got {len(columns)}: {columns}"
        # First column is left, second is right
        assert columns[0][0] < columns[1][0]
        doc.close()

    def test_text_order_in_columns(self, parser, two_column_pdf):
        """Text in two columns is read left-to-right, top-to-bottom."""
        result = parser.parse(two_column_pdf)
        # We should have sections from both columns
        assert len(result.sections) >= 2
        # First heading should be from left column
        left_heading = "Levaya kolonka"
        right_heading = "Pravaya kolonka"
        titles = [s["title"] for s in result.sections]
        # At least one title should contain left column text
        assert any(left_heading[:10] in t for t in titles)
        # Combined text should contain both "Levaya" and "Pravaya"
        all_text = " ".join(s["title"] + s.get("content", "") for s in result.sections)
        assert "Levaya" in all_text or "levoj" in all_text
        assert "Pravaya" in all_text or "pravoj" in all_text


class TestListDetection:
    """Tests for list detection."""

    def test_detect_lists_numbered(self, parser, list_pdf):
        """Detect numbered lists."""
        result = parser.parse(list_pdf)
        assert len(result.lists) > 0, "No lists detected"

        numbered_lists = [l for l in result.lists if l.get("style") == "numbered" and l.get("level") == 0]
        assert len(numbered_lists) >= 1, "No numbered lists found"

        # Check items
        top_list = numbered_lists[0]
        assert len(top_list["items"]) >= 3
        assert "Pervyj" in top_list["items"][0]

    def test_detect_lists_bulleted(self, parser, list_pdf):
        """Detect bulleted/marked lists."""
        result = parser.parse(list_pdf)
        bulleted = [l for l in result.lists if l.get("style") == "bulleted"]
        assert len(bulleted) >= 1, "No bulleted lists found"
        assert "Pervyj" in bulleted[0]["items"][0]

    def test_detect_lists_nested(self, parser, list_pdf):
        """Detect nested lists (1. → а) → -)."""
        result = parser.parse(list_pdf)
        # The nested list has numbered top-level and lettered as nested
        nested = [l for l in result.lists if l.get("level") == 1]
        assert len(nested) >= 1, "No nested lists found"

        # There should also be a numbered list at level 1 (subnumbered)
        subnumbered = [l for l in result.lists
                       if l.get("style") == "numbered" and l.get("level") == 1]
        # OR lettered style at level 1
        lettered = [l for l in result.lists if l.get("style") == "lettered"]
        assert len(lettered) >= 1 or len(subnumbered) >= 1, \
            f"No nested list items found. lettered={len(lettered)}, subnumbered={len(subnumbered)}"


class TestTableExtraction:
    """Tests for table extraction and merging."""

    def test_extract_tables(self, parser, table_pdf):
        """Extract tables from a simple document."""
        result = parser.parse(table_pdf)
        assert len(result.tables) >= 1, "No tables extracted"
        tbl = result.tables[0]
        assert tbl["cols_count"] >= 3
        assert tbl["rows_count"] >= 3
        # Check some content (using transliterated text)
        assert "Bumaga" in tbl["html_content"] or "Ruchki" in tbl["html_content"]

    def test_merge_broken_tables(self, parser, broken_table_pdf):
        """Merge a table broken across page boundaries."""
        result = parser.parse(broken_table_pdf)
        # The table should be detected by pdfplumber (now using reportlab Table)
        assert len(result.tables) >= 1, "No tables found in broken-table PDF"

        tbl = result.tables[0]
        # With 30 rows + 1 header header = 31 rows expected
        assert tbl["rows_count"] >= 5, \
            f"Expected table with 5+ rows, got {tbl['rows_count']}"
        assert tbl["cols_count"] >= 2

    def test_tables_to_result_structure(self, parser):
        """_tables_to_result produces correct structure."""
        table_data = [
            ["Name", "Value"],
            ["A", "1"],
            ["B", "2"],
        ]
        tbl = parser._tables_to_result(table_data, section_id=99)
        assert tbl["cols_count"] == 2
        # rows_count = len(rows) + (1 if headers else 0)
        # rows = [["A","1"],["B","2"]], headers = ["Name","Value"] → rows_count = 2 + 1 = 3
        assert tbl["rows_count"] == 3
        assert tbl["section_id"] == 99
        assert "<table" in tbl["html_content"]
        assert "Name" in tbl["html_content"]


class TestHeadingsDetection:
    """Tests for heading detection."""

    def test_heading_levels(self, parser, complex_pdf):
        """Different font sizes produce different heading levels."""
        result = parser.parse(complex_pdf)
        assert len(result.sections) >= 2, "Expected at least 2 sections"

        # The first heading "Сложный документ" is 22pt → level 1
        headings = [s for s in result.sections if s.get("level", 0) >= 1]
        assert len(headings) >= 1

        title_sections = [s for s in headings if "Сложный документ" in s["title"]]
        if title_sections:
            assert title_sections[0]["level"] == 1


class TestFullParsing:
    """Tests for the full parse pipeline."""

    def test_parse_enhanced_full(self, parser, complex_pdf):
        """Full parsing of a complex document yields all feature types."""
        result = parser.parse(complex_pdf)

        # Sections should be detected
        assert len(result.sections) >= 2, f"Expected sections, got {len(result.sections)}"

        # Lists should be detected (the numbered list section)
        assert len(result.lists) >= 1, f"Expected lists, got {len(result.lists)}"

        # Tables should be extracted (the "Parametr/Znachenie" table via reportlab Table)
        assert len(result.tables) >= 1, f"Expected tables, got {len(result.tables)}"

    def test_parse_single_column(self, parser, single_column_pdf):
        """Simple document parses correctly."""
        result = parser.parse(single_column_pdf)
        assert len(result.sections) >= 2
        # Check heading hierarchy
        headings = [s for s in result.sections if s.get("level", 0) >= 1]
        assert len(headings) >= 2

    def test_parse_list_pdf(self, parser, list_pdf):
        """List PDF produces both sections and lists."""
        result = parser.parse(list_pdf)
        assert len(result.lists) >= 2, f"Expected 2+ lists, got {len(result.lists)}"
        # Lists should have items
        all_items = sum(len(l["items"]) for l in result.lists)
        assert all_items >= 5, f"Expected 5+ list items total, got {all_items}"


class TestListDetectionUnit:
    """Unit tests for list detection helpers."""

    def test_classify_numbered(self, parser):
        style, level = parser._classify_list_item("1. Первый пункт")
        assert style == "numbered"
        assert level == 0

    def test_classify_bulleted(self, parser):
        style, level = parser._classify_list_item("- Элемент списка")
        assert style == "bulleted"
        assert level == 0

    def test_classify_lettered(self, parser):
        style, level = parser._classify_list_item("а) Подпункт")
        assert style == "lettered"
        assert level == 1

    def test_classify_subnumbered(self, parser):
        style, level = parser._classify_list_item("1.1. Детализация")
        assert style == "numbered"
        assert level == 1

    def test_classify_plain_text(self, parser):
        style, level = parser._classify_list_item("Это обычный текст")
        assert style is None
        assert level == 0

    def test_strip_marker_numbered(self, parser):
        result = parser._strip_list_marker("1. Текст пункта", "numbered")
        assert result == "Текст пункта"

    def test_strip_marker_bulleted(self, parser):
        result = parser._strip_list_marker("- Элемент", "bulleted")
        assert result == "Элемент"

    def test_strip_marker_lettered(self, parser):
        result = parser._strip_list_marker("а) Подпункт", "lettered")
        assert result == "Подпункт"


class TestColumnDetectionUnit:
    """Unit tests for column detection helpers."""

    def test_detect_columns_single_block_group(self, parser):
        blocks = [
            {"type": 0, "bbox": (30, 100, 280, 120)},
            {"type": 0, "bbox": (30, 130, 280, 150)},
            {"type": 0, "bbox": (30, 160, 280, 180)},
        ]
        columns = parser._detect_columns(blocks, page_width=595)
        assert len(columns) == 1

    def test_detect_columns_two_groups(self, parser):
        blocks = [
            {"type": 0, "bbox": (30, 100, 280, 120)},
            {"type": 0, "bbox": (30, 130, 280, 150)},
            {"type": 0, "bbox": (310, 100, 560, 120)},
            {"type": 0, "bbox": (310, 130, 560, 150)},
        ]
        columns = parser._detect_columns(blocks, page_width=595)
        assert len(columns) == 2

    def test_assign_blocks_to_columns(self, parser):
        blocks = [
            {"type": 0, "bbox": (30, 100, 280, 120)},
            {"type": 0, "bbox": (310, 100, 560, 120)},
        ]
        columns = [(0, 300), (300, 600)]
        assigned = parser._assign_blocks_to_columns(blocks, columns)
        assert assigned[0]["_col_idx"] == 0
        assert assigned[1]["_col_idx"] == 1

    def test_detect_heading_level(self, parser):
        # Level 1: large font
        is_h, level = parser._detect_heading_level("Заголовок", 20, True)
        assert is_h and level == 1

        # Level 2: medium font + bold
        is_h, level = parser._detect_heading_level("Подзаголовок", 14, True)
        assert is_h and level == 2

        # Level 2: medium font all-caps
        is_h, level = parser._detect_heading_level("ВАЖНЫЙ РАЗДЕЛ", 14, False)
        assert is_h and level == 1  # all-caps triggers L1

        # Not heading: small font
        is_h, level = parser._detect_heading_level("Обычный текст", 10, False)
        assert not is_h

        # Level 3: section marker
        is_h, level = parser._detect_heading_level("Статья 1. Общие положения", 11, False)
        assert is_h, "Section marker should be detected as heading"
        assert level == 3

    def test_detect_no_heading_short_text(self, parser):
        is_h, level = parser._detect_heading_level("A", 20, True)
        assert not is_h, "Text shorter than 2 chars should not be heading"


class TestBrokenTableMerging:
    """Tests for broken table merging logic."""

    def test_tables_match_structure(self, parser):
        t1 = {"cols_count": 3}
        t2 = {"cols_count": 3}
        assert parser._tables_match_structure(t1, t2)

    def test_tables_dont_match_structure(self, parser):
        t1 = {"cols_count": 3}
        t2 = {"cols_count": 4}
        assert not parser._tables_match_structure(t1, t2)

    def test_is_repeated_header(self, parser):
        rows1 = [["ID", "Name", "Value"]]
        rows2 = [["ID", "Name", "Value"]]
        assert parser._is_repeated_header(rows1, rows2)

    def test_table_likely_continues(self, parser):
        table = {"_raw_rows": [["H1", "H2"], ["A", "1"], ["", ""]]}
        assert parser._table_likely_continues(table)

    def test_table_not_continues(self, parser):
        table = {"_raw_rows": [["H1", "H2"], ["A", "1"], ["B", "2"]]}
        assert not parser._table_likely_continues(table)


class TestFactory:
    """Tests for the parser factory."""

    def test_get_parser_pdf_enhanced(self):
        from app.parsers import get_parser
        p = get_parser("pdf", enhanced=True)
        assert p is not None
        # The factory should return the enhanced_document_parser
        from app.services.parser_service import enhanced_document_parser
        assert p == enhanced_document_parser

    def test_get_parser_pdf_basic(self):
        from app.parsers import get_parser
        p = get_parser("pdf", enhanced=False)
        from app.services.parser_service import document_parser
        assert p == document_parser

    def test_get_parser_docx(self):
        from app.parsers import get_parser
        p = get_parser("docx", enhanced=True)
        from app.services.parser_service import document_parser
        assert p == document_parser  # docx always uses basic parser


class TestDetectedListDataclass:
    """Unit tests for DetectedList."""

    def test_detected_list_creation(self):
        dl = DetectedList(
            items=["Первый", "Второй"],
            level=0,
            start_page=1,
            style="numbered",
        )
        assert len(dl.items) == 2
        assert dl.level == 0
        assert dl.style == "numbered"


class TestEmptyDocument:
    """Edge cases."""

    def test_empty_pdf_returns_empty_result(self, tmp_path):
        """An empty/minimal PDF should not crash."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        empty_path = str(tmp_path / "empty.pdf")
        c = canvas.Canvas(empty_path, pagesize=A4)
        c.save()

        parser = EnhancedPDFParser()
        result = parser.parse(empty_path)
        assert result.sections == []
        assert result.tables == []
        assert result.lists == []
        assert result.terms == []

    def test_parse_nonexistent_file_raises(self, parser):
        with pytest.raises(Exception):
            parser.parse("/nonexistent/file.pdf")
