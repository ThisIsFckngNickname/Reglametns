"""
Parser service facade — re-exports all parser components.
"""
from app.parsers.helpers import ParseResult  # noqa: F401
from app.parsers.helpers import (           # noqa: F401
    _build_section_hierarchy,
    _extract_abbreviations_from_text,
    _extract_terms_from_text,
    _find_term_abbreviation_sections,
    _is_abbreviation_section,
    _is_term_section,
    _table_to_html,
)
from app.parsers.docx_parser import DocxParser      # noqa: F401
from app.parsers.pdf_parser import PdfParser         # noqa: F401
from app.parsers import (                            # noqa: F401
    DocumentParser,
    document_parser,
    enhanced_document_parser,
)
