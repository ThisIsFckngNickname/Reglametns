"""
API routes for document revision (Phase 6).

Endpoints:
- POST   /api/v1/documents/{document_id}/revise        — Create revision via LLM
- GET    /api/v1/documents/{document_id}/revisions       — List revision history
- GET    /api/v1/documents/{document_id}/revisions/{id}  — Get revision detail
- GET    /api/v1/documents/{document_id}/revisions/{id}/diff — Get revision diff
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_editor
from app.database import get_db
from app.models.user import User
from app.schemas.revision import (
    ReviseRequest,
    ReviseResponse,
    RevisionDetail,
    RevisionDiffResponse,
    RevisionHistoryItem,
)
from app.services.revision_service import revision_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["revisions"])


@router.post("/{document_id}/revise", response_model=ReviseResponse)
async def revise_document(
    document_id: int,
    body: ReviseRequest,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Revise a document based on user feedback via LLM.

    Requires editor+ role. The document must belong to the user's active company.
    """
    from fastapi import HTTPException
    from app.core.exceptions import AppException
    try:
        return await revision_service.revise_document(
            document_id=document_id,
            comment=body.comment,
            target_section=body.target_section,
            current_user=current_user,
            db=db,
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Revision failed for document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Revision failed: {str(e)}")


@router.get("/{document_id}/revisions", response_model=list[RevisionHistoryItem])
async def get_revision_history(
    document_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get revision history for a document.

    Requires active company membership. Returns newest revisions first.
    """
    return await revision_service.get_revision_history(
        document_id=document_id,
        company_id=current_user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/revisions/{revision_id}", response_model=RevisionDetail)
async def get_revision_detail(
    document_id: int,
    revision_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific revision including old/new text.

    Requires active company membership.
    """
    return await revision_service.get_revision_detail(
        document_id=document_id,
        revision_id=revision_id,
        company_id=current_user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/revisions/{revision_id}/diff", response_model=RevisionDiffResponse)
async def get_revision_diff(
    document_id: int,
    revision_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get diff for a specific revision.

    Requires active company membership.
    Returns old_text, new_text, and computed diff.
    """
    return await revision_service.get_revision_diff(
        document_id=document_id,
        revision_id=revision_id,
        company_id=current_user.active_company_id,
        db=db,
    )
