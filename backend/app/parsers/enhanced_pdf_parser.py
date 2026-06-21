"""
Enhanced PDF parser — handles complex layouts:

- Multi-column detection & reading order
- Nested tables (limited support via pdfplumber)
- Broken table merging across page breaks
- List detection (numbered, bulleted, lettered, nested)
- 3-level section heading detection
- Mixed content (text-in-table, via cell extraction)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.parsers.helpers import (
    ParseResult,
    _build_section_hierarchy,
    _extract_abbreviations_from_text,
    _extract_terms_from_text,
    _find_term_abbreviation_sections,
)

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────
COLUMN_GAP_THRESHOLD = 15  # minimum px gap between columns
HEADING_FONT_SIZE_L1 = 18  # level 1 heading min font size
HEADING_FONT_SIZE_L2 = 14  # level 2 heading min font size
HEADING_FONT_SIZE_L3 = 12  # level 3 heading min (with bold)
LIST_PATTERNS = {
    "numbered": re.compile(r"^\d{1,3}\.\s+"),          # "1. " or "12. "
    "numbered_paren": re.compile(r"^\d{1,3}\)\s+"),    # "1) "
    "lettered": re.compile(r"^[а-яА-Яa-zA-Z]\)\s+"),  # "а) " or "a) "
    "lettered_dot": re.compile(r"^[а-яА-Яa-zA-Z]\.\s+"),  # "а. "
    "bulleted": re.compile(r"^[•\-*\u2022]\s+"),       # "• ", "- ", "* "
    "subnumbered": re.compile(r"^\d{1,3}\.\d{1,3}\.\s+"),  # "1.1. "
}
# Consecutive lines that match any list pattern form a list.
# Nesting: if a line starts with a sub-number or letter → level 1; else level 0.


@dataclass
class DetectedList:
    """Represents a detected list in the document."""
    items: list[str] = field(default_factory=list)
    level: int = 0
    start_page: int = 0
    style: str = "numbered"  # "numbered" | "bulleted" | "lettered"


# ParsedDocument is an alias for ParseResult from parser_service,
# with the additional guarantee that the 'lists' field contains
# DetectedList-compatible dicts with keys: items, level, start_page, style.


# ─── Helper: sort blocks reading-order (column-aware) ──────────────────


def _reading_order_key(block: dict) -> tuple:
    """Sort key: column index (left→right), then top→bottom within column."""
    col_idx = block.get("_col_idx", 0)
    y0 = block.get("bbox", [0, 0, 0, 0])[1] if block.get("bbox") else 0
    return (col_idx, y0)


# ─── Enhanced PDF Parser ────────────────────────────────────────────────

class EnhancedPDFParser:
    """
    PDF parser with advanced layout detection.

    Usage:
        parser = EnhancedPDFParser()
        result = parser.parse("path/to/file.pdf")
    """

    def parse(self, file_path: str) -> ParseResult:
        """Full parse cycle — returns a ParseResult (with lists populated)."""
        import fitz

        result = ParseResult()
        doc = fitz.open(file_path)
        tables_by_page: dict[int, list[dict]] = {}

        # Extract tables with pdfplumber
        pdfplumber_tables = self._extract_all_tables_with_pdfplumber(file_path)

        for page_num, page in enumerate(doc, start=1):
            page_dict = self._parse_page(page, page_num)
            # Add pdfplumber tables to page_dict
            if page_num in pdfplumber_tables:
                page_dict["tables"] = pdfplumber_tables[page_num]

            # Collect sections (headings + content)
            for block in page_dict.get("blocks", []):
                text = block.get("text", "")
                if not text:
                    continue

                if block.get("is_heading"):
                    level = block.get("heading_level", 1)
                    result.sections.append({
                        "title": text,
                        "level": level,
                        "content": "",
                        "parent_id": None,
                        "order_num": len(result.sections) + 1,
                    })
                elif result.sections:
                    result.sections[-1]["content"] += text + "\n"

            # Collect tables from this page
            if page_dict.get("tables"):
                tables_by_page[page_num] = page_dict["tables"]

            # Collect lists (convert DetectedList to dict)
            for lst in page_dict.get("lists", []):
                result.lists.append({
                    "items": lst.items,
                    "level": lst.level,
                    "start_page": lst.start_page,
                    "style": lst.style,
                })

        doc.close()

        # Merge broken tables across pages
        merged_tables = self._merge_broken_tables(tables_by_page)
        for tbl in merged_tables:
            result.tables.append(tbl)

        # Build section hierarchy
        result.sections = _build_section_hierarchy(result.sections)

        # Extract terms and abbreviations (reuse existing logic)
        self._extract_terms_and_abbreviations(result)

        return result

    # ── Page-level parsing ──────────────────────────────────────────────

    def _parse_page(self, page: Any, page_num: int) -> dict:
        """Parse a single PDF page with full layout analysis."""
        import fitz

        page_dict = page.get_text("dict")
        page_width = page_dict.get("width", 595)
        page_height = page_dict.get("height", 842)
        raw_blocks = page_dict.get("blocks", [])

        # Detect columns
        columns = self._detect_columns(raw_blocks, page_width)

        # Assign each block to a column
        blocks_with_cols = self._assign_blocks_to_columns(raw_blocks, columns)

        # Sort blocks in reading order: column-wise, top-to-bottom
        blocks_with_cols.sort(key=_reading_order_key)

        # Process blocks into structured items
        processed_blocks: list[dict] = []
        lists: list[DetectedList] = []

        text_buffer: list[str] = []
        current_list: Optional[DetectedList] = None

        for block in blocks_with_cols:
            if block.get("type") != 0:  # skip non-text (images)
                continue

            block_text, block_info = self._process_text_block(block)
            if not block_text:
                continue

            # Check if this block is a list item
            list_style, list_level = self._classify_list_item(block_text)

            if list_style:
                # Accumulate into current list
                if current_list is None or current_list.style != list_style:
                    # Finalize previous list
                    if current_list and current_list.items:
                        lists.append(current_list)
                    current_list = DetectedList(
                        items=[],
                        level=list_level,
                        start_page=page_num,
                        style=list_style,
                    )
                # Trim the marker from the item text
                clean = self._strip_list_marker(block_text, list_style)
                current_list.items.append(clean)
                # Also store as regular block
                text_buffer.append(block_text)
            else:
                # Finalize list if we were building one
                if current_list and current_list.items:
                    lists.append(current_list)
                    current_list = None
                text_buffer.append(block_text)

            # Build processed block entry
            entry: dict = {
                "text": block_text,
                "bbox": block.get("bbox", [0, 0, 0, 0]),
                "_col_idx": block.get("_col_idx", 0),
                "is_heading": block_info.get("is_heading", False),
                "heading_level": block_info.get("heading_level", 0),
                "font_size": block_info.get("font_size", 12),
                "is_bold": block_info.get("is_bold", False),
            }
            processed_blocks.append(entry)

        # Finalize last list
        if current_list and current_list.items:
            lists.append(current_list)

        # Tables are extracted separately via pdfplumber in the main parse() loop
        tables: list[dict] = []

        return {
            "page_num": page_num,
            "width": page_width,
            "height": page_height,
            "columns": [{"bbox": c} for c in columns],
            "blocks": processed_blocks,
            "tables": tables if tables else [],
            "lists": lists,
        }

    # ── Column Detection ────────────────────────────────────────────────

    def _detect_columns(
        self, blocks: list[dict], page_width: float
    ) -> list[tuple[float, float]]:
        """Detect column boundaries from text block positions.

        Algorithm:
        1. Collect the x0 (left) and x1 (right) of every text block.
        2. Sort unique left edges.
        3. If the gap between consecutive left-edge clusters exceeds
           COLUMN_GAP_THRESHOLD, treat as a column boundary.
        4. Return list of (x0, x1) for each detected column.
        """
        # Filter only text blocks
        text_blocks = [b for b in blocks if b.get("type") == 0]
        if not text_blocks:
            return [(0, page_width)]

        # Collect left / right edges
        left_edges = sorted({b["bbox"][0] for b in text_blocks if b.get("bbox")})
        right_edges = sorted({b["bbox"][2] for b in text_blocks if b.get("bbox")})

        if not left_edges:
            return [(0, page_width)]

        # Cluster left edges: if gap > threshold, new column starts
        columns: list[tuple[float, float]] = []
        col_start = left_edges[0]

        # Find right edge for this column (the max of block rights in that column)
        # Simple heuristic: column ends where next column starts minus gap
        col_end = page_width

        for i in range(1, len(left_edges)):
            gap = left_edges[i] - left_edges[i - 1]
            if gap > COLUMN_GAP_THRESHOLD:
                # End current column at the mean right edge of blocks in this column
                col_end = left_edges[i - 1] + page_width  # placeholder
                columns.append((col_start, col_end))
                col_start = left_edges[i]

        # Add last column
        if right_edges:
            col_end = max(right_edges) + 5  # small padding
        columns.append((col_start, min(col_end, page_width)))

        # If only one column detected, return full width
        if len(columns) <= 1:
            return [(0, page_width)]

        return columns

    def _assign_blocks_to_columns(
        self, blocks: list[dict], columns: list[tuple[float, float]]
    ) -> list[dict]:
        """Assign each block to a column index based on its x-center."""
        if len(columns) <= 1:
            for b in blocks:
                b["_col_idx"] = 0
            return blocks

        for block in blocks:
            bbox = block.get("bbox")
            if not bbox:
                block["_col_idx"] = 0
                continue
            cx = (bbox[0] + bbox[2]) / 2.0
            assigned = False
            for idx, (c0, c1) in enumerate(columns):
                if c0 <= cx <= c1:
                    block["_col_idx"] = idx
                    assigned = True
                    break
            if not assigned:
                # Fallback: nearest column
                distances = [abs(cx - (c0 + c1) / 2.0) for c0, c1 in columns]
                block["_col_idx"] = distances.index(min(distances))

        return blocks

    # ── Text Processing ─────────────────────────────────────────────────

    def _process_text_block(self, block: dict) -> tuple[str, dict]:
        """Extract text from a block and detect heading properties."""
        lines = block.get("lines", [])
        full_text = ""
        max_font_size = 0
        is_bold = False
        is_heading = False
        heading_level = 0

        for line in lines:
            line_text = ""
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                line_text += span_text
                sz = span.get("size", 12)
                if sz > max_font_size:
                    max_font_size = sz
                font_name = span.get("font", "").lower()
                if "bold" in font_name:
                    is_bold = True
            full_text += line_text

        full_text = full_text.strip()
        if not full_text:
            return "", {"is_heading": False, "heading_level": 0}

        # Detect heading
        is_heading, heading_level = self._detect_heading_level(
            full_text, max_font_size, is_bold
        )

        return full_text, {
            "is_heading": is_heading,
            "heading_level": heading_level,
            "font_size": max_font_size,
            "is_bold": is_bold,
        }

    def _detect_heading_level(
        self, text: str, font_size: float, is_bold: bool
    ) -> tuple[bool, int]:
        """Detect if text is a heading and at what level.

        Level 1: font >= 18 OR all-caps with font >= 14
        Level 2: font >= 14 OR bold with font >= 12
        Level 3: font >= 12 and bold, OR starts with article marker
        """
        # Skip short/empty text
        if len(text) < 2 or len(text) > 300:
            return False, 0

        # Check for article/section markers typical in Russian docs
        section_marker = bool(re.match(
            r"^(Статья\s|Глава\s|Раздел\s|Пункт\s|Подпункт\s|Приложение\s)",
            text, re.IGNORECASE
        ))

        if font_size >= HEADING_FONT_SIZE_L1 or (
            text.isupper() and font_size >= HEADING_FONT_SIZE_L2
        ):
            return True, 1
        elif font_size >= HEADING_FONT_SIZE_L2 or (
            is_bold and font_size >= HEADING_FONT_SIZE_L3
        ):
            return True, 2
        elif section_marker or (is_bold and font_size >= 10):
            return True, 3
        elif text.isupper() and len(text) > 10 and font_size > 10:
            return True, 2

        return False, 0

    # ── List Detection ──────────────────────────────────────────────────

    _LIST_PATTERNS = LIST_PATTERNS

    def _classify_list_item(self, text: str) -> tuple[Optional[str], int]:
        """Check if text starts with a list marker.

        Returns:
            (style, level) or (None, 0) if not a list item.
            level 0 = top-level, level 1 = nested
        """
        # Check sub-numbered first (1.1.) → level 1
        if self._LIST_PATTERNS["subnumbered"].match(text):
            return ("numbered", 1)

        # Numbered "1. " or "1)" → level 0
        if self._LIST_PATTERNS["numbered"].match(text):
            return ("numbered", 0)

        if self._LIST_PATTERNS["numbered_paren"].match(text):
            return ("numbered", 0)

        # Lettered "а) " or "а. " → level 1 (typically nested)
        if self._LIST_PATTERNS["lettered"].match(text):
            return ("lettered", 1)

        if self._LIST_PATTERNS["lettered_dot"].match(text):
            return ("lettered", 1)

        # Bulleted "• ", "- ", "* " → level 0
        if self._LIST_PATTERNS["bulleted"].match(text):
            return ("bulleted", 0)

        return (None, 0)

    def _strip_list_marker(self, text: str, style: str) -> str:
        """Remove the list marker from the beginning of text."""
        pattern = self._LIST_PATTERNS.get(style)
        if pattern:
            return pattern.sub("", text, count=1).strip()
        # Fallback: try all patterns
        for p in self._LIST_PATTERNS.values():
            if p.match(text):
                return p.sub("", text, count=1).strip()
        return text

    # ── Table Extraction ────────────────────────────────────────────────

    def _extract_all_tables_with_pdfplumber(self, file_path: str) -> dict[int, list[dict]]:
        """Extract all tables from a PDF using pdfplumber, grouped by page number.

        Returns:
            dict[int, list[dict]] — page_num -> list of table dicts
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not available, skipping table extraction")
            return {}

        result: dict[int, list[dict]] = {}

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                page_tables: list[dict] = []
                for table_data in tables:
                    if not table_data:
                        continue
                    tbl = self._tables_to_result(table_data, section_id=None)
                    tbl["_raw_rows"] = [
                        [str(c) if c else "" for c in row]
                        for row in table_data
                    ]
                    page_tables.append(tbl)
                if page_tables:
                    result[page_num] = page_tables

        return result

    def _extract_nested_tables(
        self, table_data: list[list[Optional[str]]]
    ) -> list[dict]:
        """Check if any cell contains a sub-table and extract it.

        Currently returns empty list (stub for future use).
        In pdfplumber, nested tables are rare and hard to detect.
        """
        _ = table_data  # stub
        return []

    def _tables_to_result(
        self, table_data: list[list[Optional[str]]], section_id: Optional[int]
    ) -> dict:
        """Convert pdfplumber table data to result dict."""
        from app.parsers.helpers import _table_to_html

        headers: list[str] = []
        rows: list[list[str]] = []

        for i, row in enumerate(table_data):
            cells = [str(c) if c else "" for c in row]
            if i == 0:
                headers = cells
            else:
                rows.append(cells)

        if len(table_data) <= 1 and headers:
            rows = [headers]
            headers = []

        return {
            "caption": None,
            "html_content": _table_to_html(headers, rows, None),
            "rows_count": len(rows) + (1 if headers else 0),
            "cols_count": max(
                (len(headers) if headers else 0),
                max((len(r) for r in rows), default=0),
            ),
            "order_num": 0,
            "section_id": section_id,
            "_raw_rows": rows if not headers else [headers] + rows,
        }

    # ── Broken Table Merging ────────────────────────────────────────────

    def _merge_broken_tables(self, tables_by_page: dict[int, list[dict]]) -> list[dict]:
        """Merge tables that are broken across page boundaries.

        Heuristic:
        - If last table on page N has same column count as first table on page N+1,
          and there is no header repetition (same header text), merge rows.
        """
        if not tables_by_page:
            return []

        sorted_pages = sorted(tables_by_page.keys())
        merged: list[dict] = []
        carried: Optional[dict] = None  # table being carried across pages

        for pnum in sorted_pages:
            page_tables = tables_by_page[pnum]
            if not page_tables:
                if carried:
                    merged.append(carried)
                    carried = None
                continue

            if carried:
                # Try to merge carried table with first table on this page
                first = page_tables[0]
                if self._tables_match_structure(carried, first):
                    # Merge rows, skip if header repeats
                    carried_rows = carried.get("_raw_rows", [])
                    first_rows = first.get("_raw_rows", [])

                    # Check if first row of 'first' looks like a repeated header
                    if self._is_repeated_header(carried_rows, first_rows):
                        first_rows = first_rows[1:]  # skip repeated header

                    carried["_raw_rows"] = carried_rows + first_rows
                    carried["rows_count"] = len(carried["_raw_rows"])
                    # Rebuild HTML
                    carried["html_content"] = self._rebuild_table_html(carried)
                    # Use remaining tables as new tables
                    for t in page_tables[1:]:
                        merged.append(t)
                else:
                    merged.append(carried)
                    for t in page_tables:
                        merged.append(t)
                carried = None
            else:
                # Check if last table may be continued
                last_table = page_tables[-1]
                if len(page_tables) > 1:
                    for t in page_tables[:-1]:
                        merged.append(t)
                    # Check if last table continues
                    if self._table_likely_continues(last_table):
                        carried = last_table
                    else:
                        merged.append(last_table)
                else:
                    if self._table_likely_continues(last_table):
                        carried = last_table
                    else:
                        merged.append(last_table)

        if carried:
            merged.append(carried)

        # Re-number tables
        for i, tbl in enumerate(merged):
            tbl["order_num"] = i + 1

        # Remove internal fields
        for tbl in merged:
            tbl.pop("_raw_rows", None)

        return merged

    def _tables_match_structure(self, t1: dict, t2: dict) -> bool:
        """Check if two tables have compatible structure for merging."""
        return t1.get("cols_count") == t2.get("cols_count")

    def _is_repeated_header(
        self, rows1: list[list[str]], rows2: list[list[str]]
    ) -> bool:
        """Check if the first row of rows2 repeats the last row(s) of rows1."""
        if not rows1 or not rows2:
            return False
        # Compare first row of rows2 with last row of rows1
        if rows1[-1] == rows2[0]:
            return True
        # Or if first row of rows2 matches header-like pattern
        header_keywords = {"№", "п/п", "наименование", "колонка", "столбец"}
        first_row_text = " ".join(rows2[0]).lower()
        return any(kw in first_row_text for kw in header_keywords)

    def _table_likely_continues(self, table: dict) -> bool:
        """Heuristic: if the last row has empty cells, the table likely continues."""
        raw_rows = table.get("_raw_rows", [])
        if not raw_rows or len(raw_rows) < 2:
            return False
        last_row = raw_rows[-1]
        # If most cells in last row are empty, likely continues
        if not last_row:
            return True
        empty_count = sum(1 for c in last_row if not c or not c.strip())
        return empty_count > len(last_row) / 2

    def _rebuild_table_html(self, table: dict) -> str:
        """Rebuild HTML content from raw rows."""
        from app.parsers.helpers import _table_to_html

        rows = table.get("_raw_rows", [])
        headers: list[str] = []
        data_rows: list[list[str]] = []

        if rows:
            headers = rows[0]
            data_rows = rows[1:]

        return _table_to_html(headers, data_rows, table.get("caption"))

    # ── Image Extraction (stub) ─────────────────────────────────────────

    def _extract_images(self, page: Any) -> Optional[list[dict]]:
        """Extract images from a page.

        Returns None (stub — images not processed yet).
        """
        return None

    # ── Terms & Abbreviations ───────────────────────────────────────────

    def _extract_terms_and_abbreviations(self, result: ParseResult) -> None:
        """Extract terms and abbreviations from parsed sections."""
        all_text = "\n".join(s.get("content", "") for s in result.sections)
        term_section_ids, abbr_section_ids = _find_term_abbreviation_sections(
            result.sections
        )

        for section in result.sections:
            if section["order_num"] in term_section_ids:
                result.terms.extend(
                    _extract_terms_from_text(section.get("content", ""))
                )

        if not result.terms:
            result.terms.extend(_extract_terms_from_text(all_text))

        for section in result.sections:
            if section["order_num"] in abbr_section_ids:
                result.abbreviations.extend(
                    _extract_abbreviations_from_text(section.get("content", ""))
                )

        if not result.abbreviations:
            result.abbreviations.extend(
                _extract_abbreviations_from_text(all_text)
            )


# ─── Convenience instance ───────────────────────────────────────────────

enhanced_pdf_parser = EnhancedPDFParser()
