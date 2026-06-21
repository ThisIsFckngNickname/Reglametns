"""
Document service facade — combines all document operations.

This module imports specialized sub-services and composes them via
multiple inheritance into a single DocumentService class for backward
compatibility.
"""

from app.services.document_read_service import DocumentReadService
from app.services.document_upload_service import DocumentUploadService
from app.services.document_update_service import DocumentUpdateService


class DocumentService(
    DocumentReadService,
    DocumentUploadService,
    DocumentUpdateService,
):
    """Facade combining all document operations."""
    pass


document_service = DocumentService()
