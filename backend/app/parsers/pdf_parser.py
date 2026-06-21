"""
PDF parser — parse PDF files using PyMuPDF (fitz) + pdfplumber.
"""
import logging

from app.parsers.helpers import (
    ParseResult,
    _build_section_hierarchy,
    _extract_abbreviations_from_text,
    _extract_terms_from_text,
    _find_term_abbreviation_sections,
    _table_to_html,
)

logger = logging.getLogger(__name__)


class PdfParser:
    """Parse PDF files using PyMuPDF (fitz) + pdfplumber."""

    def parse(self, file_path: str) -> ParseResult:
        """Parse a PDF file and return its structure."""
        result = ParseResult()
        all_text = ""

        # Step 1: Extract text with PyMuPDF
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF (fitz) is required to parse PDF files")

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            logger.warning(f"Failed to open PDF with PyMuPDF: {e}")
            return result

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict").get("blocks", [])
            page_text_lines = []

            for block in blocks:
                if block.get("type") != 0:  # skip images
                    continue

                for line in block.get("lines", []):
                    line_text = ""
                    font_size = None
                    is_bold = False

                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        if font_size is None:
                            font_size = span.get("size", 12)
                        font_name = span.get("font", "").lower()
                        if "bold" in font_name:
                            is_bold = True

                    line_text = line_text.strip()
                    if not line_text:
                        continue

                    page_text_lines.append(line_text)

                    # Detect heading: large font (>14) or bold+large
                    is_heading = (
                        (font_size and font_size > 14)
                        or (is_bold and font_size and font_size > 12)
                        or (line_text.isupper() and len(line_text) > 3 and len(line_text) < 200)
                    )

                    if is_heading and len(line_text) < 200:
                        level = 1
                        if font_size:
                            if font_size <= 14:
                                level = 2
                            elif font_size <= 18:
                                level = 1
                            else:
                                level = 1

                        result.sections.append({
                            "title": line_text,
                            "level": level,
                            "content": "",
                            "parent_id": None,
                            "order_num": len(result.sections) + 1,
                        })
                    elif result.sections:
                        result.sections[-1]["content"] += line_text + "\n"

            all_text += "\n".join(page_text_lines) + "\n"

        doc.close()

        # Step 2: Extract tables with pdfplumber
        try:
            self._extract_pdf_tables(file_path, result)
        except Exception as e:
            logger.warning(f"Failed to extract tables with pdfplumber: {e}")

        # Build hierarchy
        result.sections = _build_section_hierarchy(result.sections)

        # Extract terms and abbreviations
        term_section_ids, abbr_section_ids = _find_term_abbreviation_sections(result.sections)

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
            result.abbreviations.extend(_extract_abbreviations_from_text(all_text))

        return result

    def _extract_pdf_tables(self, file_path: str, result: ParseResult) -> None:
        """Extract tables from PDF using pdfplumber."""
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not available, skipping table extraction")
            return

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table_data in tables:
                    if not table_data:
                        continue

                    headers = []
                    rows = []
                    for i, row in enumerate(table_data):
                        cells = [str(c) if c else "" for c in row]
                        if i == 0:
                            headers = cells
                        else:
                            rows.append(cells)

                    if len(table_data) <= 1 and headers:
                        rows = [headers]
                        headers = []

                    section_id = result.sections[-1]["order_num"] if result.sections else None

                    result.tables.append({
                        "caption": None,
                        "html_content": _table_to_html(headers, rows, None),
                        "rows_count": len(rows) + (1 if headers else 0),
                        "cols_count": max(
                            (len(headers) if headers else 0),
                            max((len(r) for r in rows), default=0),
                        ),
                        "order_num": len(result.tables) + 1,
                        "section_id": section_id,
                    })
