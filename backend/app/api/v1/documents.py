"""
API router for document endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_holding
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import (
    DocumentListItem,
    DocumentResponse,
    DocumentSectionResponse,
    DocumentUpdate,
    PaginatedResponse,
    UploadResponse,
    VersionDiffResponse,
)
from app.services.document_service import document_service
from app.services.storage_service import storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (Word .docx or PDF), parse it, and store all extracted data."""
    result = await document_service.upload(
        file=file,
        title=title,
        description=description,
        user=user,
        holding_id=user.active_holding_id,
        db=db,
    )
    return result


@router.get("", response_model=PaginatedResponse[DocumentListItem])
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and optional filtering."""
    result = await document_service.list_documents(
        holding_id=user.active_holding_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
        db=db,
    )
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get full document metadata including counts of related entities."""
    return await document_service.get_document(
        id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    body: DocumentUpdate,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Update document metadata (title, description, status)."""
    return await document_service.update_document(
        id=document_id,
        data=body,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.delete("/{document_id}", status_code=204)
async def archive_document(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Archive a document (set status to 'archived')."""
    await document_service.archive_document(
        id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )
    return Response(status_code=204)


@router.get("/{document_id}/versions", response_model=List[dict])
async def get_document_versions(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a document."""
    return await document_service.get_versions(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.get("/versions/{version_id}/download")
async def download_version(
    version_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Download a specific version of a document file."""
    # Get the version
    stmt = select(DocumentVersion).where(DocumentVersion.id == version_id)
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()

    if version is None:
        raise NotFoundException(message="Version not found", field="version_id")

    # Verify document belongs to user's holding
    doc_stmt = select(Document).where(
        Document.id == version.document_id,
        Document.holding_id == user.active_holding_id,
    )
    doc_result = await db.execute(doc_stmt)
    if doc_result.scalar_one_or_none() is None:
        raise NotFoundException(message="Document not found", field="document_id")

    # Read file
    try:
        file_bytes = await storage.get(version.file_path)
    except FileNotFoundError:
        raise NotFoundException(message="File not found on disk")

    filename = f"document_v{version.version_number}.{version.file_type}"
    return StreamingResponse(
        content=iter([file_bytes]),
        media_type=version.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes)),
        },
    )


@router.get("/{document_id}/sections", response_model=List[DocumentSectionResponse])
async def get_document_sections(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get the section tree of a document (from the latest version)."""
    return await document_service.get_sections_tree(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.get("/{document_id}/terms", response_model=List[dict])
async def get_document_terms(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get all terms and definitions extracted from a document."""
    return await document_service.get_terms(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.get("/{document_id}/abbreviations", response_model=List[dict])
async def get_document_abbreviations(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get all abbreviations extracted from a document."""
    return await document_service.get_abbreviations(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.post("/{document_id}/versions", status_code=201)
async def create_document_version(
    document_id: int,
    file: UploadFile = File(...),
    version_notes: Optional[str] = Form(None),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of a document by uploading a new file."""
    return await document_service.create_version(
        document_id=document_id,
        file=file,
        version_notes=version_notes,
        user=user,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.get("/{document_id}/diff")
async def diff_document_versions(
    document_id: int,
    from_version: int = Query(..., description="Base version number"),
    to_version: int = Query(..., description="Target version number"),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Compare two versions of a document and show differences."""
    return await document_service.diff_versions(
        document_id=document_id,
        from_version=from_version,
        to_version=to_version,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.get("/{document_id}/tables", response_model=List[dict])
async def get_document_tables(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get all tables extracted from a document (from the latest version)."""
    return await document_service.get_tables(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )
