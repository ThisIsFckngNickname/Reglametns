"""
Parser factory — returns the appropriate parser for the given file type.
"""

from app.services.parser_service import (
    DocumentParser,
    document_parser,
    enhanced_document_parser,
)


def get_parser(file_type: str, enhanced: bool = True) -> DocumentParser:
    """Return a parser instance for the given file type.

    Args:
        file_type: "pdf" or "docx"
        enhanced: If True and file_type == "pdf", returns an enhanced parser.

    Returns:
        A DocumentParser instance implementing .parse(file_path, file_type) -> ParseResult
    """
    if file_type == "pdf" and enhanced:
        return enhanced_document_parser
    return document_parser


__all__ = ["get_parser"]
