"""
Parser factory — returns the appropriate parser for the given file type.
"""
from app.parsers.helpers import ParseResult
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser


class DocumentParser:
    """Facade that picks the right parser based on file type."""

    def __init__(self, enhanced: bool = False):
        self._enhanced = enhanced

    def parse(self, file_path: str, file_type: str) -> ParseResult:
        if file_type == "pdf" and self._enhanced:
            try:
                from app.parsers.enhanced_pdf_parser import EnhancedPDFParser
                return EnhancedPDFParser().parse(file_path)
            except ImportError:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("EnhancedPDFParser not available, falling back to default PDF parser")

        if file_type == "docx":
            return DocxParser().parse(file_path)
        elif file_type == "pdf":
            return PdfParser().parse(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")


# Convenience instances
document_parser = DocumentParser(enhanced=False)
enhanced_document_parser = DocumentParser(enhanced=True)


def get_parser(file_type: str, enhanced: bool = True) -> DocumentParser:
    """Return a parser instance for the given file type."""
    if file_type == "pdf" and enhanced:
        return enhanced_document_parser
    return document_parser


__all__ = [
    "get_parser", "ParseResult", "DocumentParser",
    "document_parser", "enhanced_document_parser",
    "DocxParser", "PdfParser",
]
