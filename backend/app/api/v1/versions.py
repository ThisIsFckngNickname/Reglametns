"""
API routes for Phase 7 — document versioning.

Provides new endpoints for:
- Downloading a specific version by version number
- Restoring a previous version
- Comparing two versions (diff)

Existing version endpoints (GET/POST /documents/{id}/versions,
GET /documents/{id}/analyses) are in documents.py and analysis.py
and have been upgraded to use VersionService internally.
"""

import logging
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_company, require_editor
from app.database import get_db
from app.models.user import User
from app.schemas.revision import DiffResult
from app.services.version_service import version_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["versions"])


@router.get("/{document_id}/versions/{version_number}/download")
async def download_version_by_number(
    document_id: int,
    version_number: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Download a specific version of a document by version number.

    Contrast with GET /documents/versions/{version_id}/download
    which downloads by internal version ID.
    """
    content, filename, content_type = await version_service.download_version(
        document_id=document_id,
        version_number=version_number,
        company_id=current_user.active_company_id,
        db=db,
    )

    return StreamingResponse(
        BytesIO(content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


@router.post("/{document_id}/versions/{version_number}/restore", status_code=201)
async def restore_version(
    document_id: int,
    version_number: int,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Restore a specific version (creates a new version with its content).

    The new version gets version_number = max + 1 and
    version_notes = "Восстановлено из версии v{N}".
    """
    new_version = await version_service.restore_version(
        document_id=document_id,
        version_number=version_number,
        company_id=current_user.active_company_id,
        author_id=current_user.id,
        db=db,
    )

    return {
        "id": new_version.id,
        "document_id": new_version.document_id,
        "version_number": new_version.version_number,
        "file_type": new_version.file_type,
        "file_size": new_version.file_size,
        "file_hash": new_version.file_hash,
        "version_notes": new_version.version_notes,
        "created_at": new_version.created_at.isoformat() if new_version.created_at else None,
        "restored_from": version_number,
    }


@router.get("/{document_id}/versions/{v1}/diff/{v2}", response_model=DiffResult)
async def compare_versions(
    document_id: int,
    v1: int,
    v2: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Compare two versions and return diff.

    Uses DiffService to generate unified diff, HTML diff, and statistics.
    Requires both versions to have extractable text content.
    """
    result = await version_service.compare_versions(
        document_id=document_id,
        version_a=v1,
        version_b=v2,
        company_id=current_user.active_company_id,
        db=db,
    )
    return result
