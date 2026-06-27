"""
API router for document endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_admin
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
)
from app.schemas.links import DocumentLinkCreate
from app.services.document_service import document_service
from app.services.storage_service import storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (Word .docx or PDF), parse it, and store all extracted data."""
    result = await document_service.upload(
        file=file,
        title=title,
        description=description,
        user=user,
        company_id=user.active_company_id,
        db=db,
    )
    return result


@router.get("", response_model=PaginatedResponse[DocumentListItem])
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and optional filtering."""
    result = await document_service.list_documents(
        company_id=user.active_company_id,
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
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get full document metadata including counts of related entities."""
    return await document_service.get_document(
        id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    body: DocumentUpdate,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Update document metadata (title, description, status)."""
    return await document_service.update_document(
        id=document_id,
        data=body,
        company_id=user.active_company_id,
        db=db,
        user_id=user.id,
    )


@router.delete("/{document_id}", status_code=204)
async def archive_document(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Archive a document (set status to 'archived')."""
    await document_service.archive_document(
        id=document_id,
        company_id=user.active_company_id,
        db=db,
    )
    return Response(status_code=204)


@router.delete("/admin/{document_id}", status_code=204)
async def hard_delete_document(
    document_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a document and all its versions from DB and storage.

    Admin-only endpoint. Requires admin privileges in any holding.
    This is a hard delete - unlike the regular DELETE which only archives.
    """
    await document_service.hard_delete_document(
        id=document_id,
        db=db,
    )
    return Response(status_code=204)


@router.get("/{document_id}/versions", response_model=List[dict])
async def get_document_versions(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a document."""
    return await document_service.get_versions(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/versions/{version_id}/download")
async def download_version(
    version_id: int,
    user: User = Depends(require_active_company),
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
        Document.company_id == user.active_company_id,
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
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get the section tree of a document (from the latest version)."""
    return await document_service.get_sections_tree(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/terms", response_model=List[dict])
async def get_document_terms(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get all terms and definitions extracted from a document."""
    return await document_service.get_terms(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/abbreviations", response_model=List[dict])
async def get_document_abbreviations(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get all abbreviations extracted from a document."""
    return await document_service.get_abbreviations(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.post("/{document_id}/versions", status_code=201)
async def create_document_version(
    document_id: int,
    file: UploadFile = File(...),
    version_notes: Optional[str] = Form(None),
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of a document by uploading a new file."""
    return await document_service.create_version(
        document_id=document_id,
        file=file,
        version_notes=version_notes,
        user=user,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/tables", response_model=List[dict])
async def get_document_tables(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get all tables extracted from a document (from the latest version)."""
    return await document_service.get_tables(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.post("/{document_id}/analyze")
async def analyze_document(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger pattern analysis for a document.

    Extracts structure, style patterns, and collects terms/abbreviations
    from the document's latest version, updating the company profile.
    """
    return await document_service.analyze_document(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.post("/analyze-batch")
async def analyze_documents_batch(
    body: dict,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Analyze multiple documents at once.
    
    Body: {"document_ids": [1, 2, 3]}
    Returns summary of analysis results for each document.
    """
    from app.services.pattern_analysis_service import pattern_analysis_service
    
    document_ids = body.get("document_ids", [])
    if not isinstance(document_ids, list) or len(document_ids) == 0:
        return {"results": [], "total": 0, "successful": 0, "failed": 0}
    
    results = []
    successful = 0
    failed = 0
    
    for doc_id in document_ids:
        try:
            # Verify ownership
            stmt = select(Document).where(
                Document.id == doc_id,
                Document.company_id == user.active_company_id,
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            
            if doc is None:
                results.append({"document_id": doc_id, "status": "error", "message": "Document not found"})
                failed += 1
                continue
            
            analysis_result = await pattern_analysis_service.analyze_document(
                document_id=doc_id,
                db=db,
            )
            
            if "error" in analysis_result:
                results.append({
                    "document_id": doc_id,
                    "status": "skipped" if analysis_result.get("already_analyzed") else "error",
                    "message": analysis_result["error"],
                })
                if not analysis_result.get("already_analyzed"):
                    failed += 1
                else:
                    successful += 1  # Already analyzed counts as OK
            else:
                results.append({
                    "document_id": doc_id,
                    "status": "success",
                    "message": "Document analyzed successfully",
                    "structure_extracted": analysis_result.get("structure_extracted", False),
                    "style_extracted": analysis_result.get("style_extracted", False),
                    "terms_collected": analysis_result.get("terms_collected", 0),
                    "abbreviations_collected": analysis_result.get("abbreviations_collected", 0),
                })
                successful += 1
        except Exception as e:
            results.append({"document_id": doc_id, "status": "error", "message": str(e)})
            failed += 1
    
    return {
        "results": results,
        "total": len(document_ids),
        "successful": successful,
        "failed": failed,
    }


@router.get("/{document_id}/links", response_model=List[dict])
async def get_outgoing_links(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get outgoing links from a document (documents it references)."""
    return await document_service.get_outgoing_links(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/links/incoming", response_model=List[dict])
async def get_incoming_links(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get incoming links to a document (documents that reference it)."""
    return await document_service.get_incoming_links(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.post("/{document_id}/links", status_code=201)
async def create_link(
    document_id: int,
    body: DocumentLinkCreate,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Create a link from this document to another document.

    Link types:
    - references: документ ссылается на другой
    - amends: документ вносит изменения в другой
    - supersedes: документ заменяет другой
    - related: документы связаны тематически
    """
    return await document_service.create_link(
        document_id=document_id,
        data=body,
        user_id=user.id,
        company_id=user.active_company_id,
        db=db,
    )


@router.delete("/{document_id}/links/{link_id}", status_code=204)
async def delete_link(
    document_id: int,
    link_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Delete a link from this document."""
    await document_service.delete_link(
        document_id=document_id,
        link_id=link_id,
        company_id=user.active_company_id,
        db=db,
    )
    return Response(status_code=204)
