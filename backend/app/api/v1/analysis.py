"""
API router for analysis pipeline endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_editor
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.database import get_db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.analysis import (
    AnalysisHistoryItem,
    AnalysisStatusResponse,
    ReanalyzeResponse,
)
from app.services.analysis_pipeline_service import (
    analysis_pipeline_service,
)

router = APIRouter(tags=["analysis"])


@router.get(
    "/documents/{document_id}/analyses",
    response_model=list[AnalysisHistoryItem],
)
async def get_analysis_history(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis history for a document.

    Returns a list of analysis records ordered by creation time (newest first).
    """
    # Verify document belongs to user's company
    stmt = select(Document).where(
        Document.id == document_id,
        Document.company_id == user.active_company_id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundException(message="Document not found", field="document_id")

    history = await analysis_pipeline_service.get_history(
        document_id=document_id,
        db=db,
    )
    return history


@router.get(
    "/analysis/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
)
async def get_analysis_status(
    analysis_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed status of an analysis pipeline run (per-step)."""
    # Load analysis
    stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise NotFoundException(message="Analysis not found", field="analysis_id")

    # Verify document belongs to user's company
    doc_stmt = select(Document).where(
        Document.id == analysis.document_id,
        Document.company_id == user.active_company_id,
    )
    doc_result = await db.execute(doc_stmt)
    if doc_result.scalar_one_or_none() is None:
        raise ForbiddenException(
            message="You do not have access to this analysis"
        )

    status_data = await analysis_pipeline_service.get_status(
        analysis_id=analysis_id,
        db=db,
    )
    if status_data is None:
        raise NotFoundException(message="Analysis not found", field="analysis_id")

    return status_data


@router.post(
    "/documents/{document_id}/reanalyze",
    status_code=202,
    response_model=ReanalyzeResponse,
)
async def reanalyze_document(
    document_id: int,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Force re-analysis of a document. Clears idempotency protection."""
    # Verify document exists and belongs to user's company
    stmt = select(Document).where(
        Document.id == document_id,
        Document.company_id == user.active_company_id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundException(message="Document not found", field="document_id")

    # Check if already running
    if doc.analysis_status == "running":
        raise ConflictException(
            message=(
                "Analysis is already running for this document. "
                "Wait for completion or check status at "
                "GET /api/v1/analysis/{id}/status"
            ),
            field=None,
        )

    # Get latest version to verify text exists
    version_stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    version_result = await db.execute(version_stmt)
    latest_version = version_result.scalar_one_or_none()

    if latest_version is None or not latest_version.full_text:
        raise BadRequestException(
            code="NO_CONTENT",
            message=(
                "Document has no extracted text. "
                "Upload a new version with parseable content."
            ),
            field="document_id",
        )

    # Trigger forced analysis
    analysis_id = await analysis_pipeline_service.trigger_analysis(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
        force=True,
    )

    if analysis_id is None:
        raise BadRequestException(
            message="Failed to start analysis. Check document content.",
            field="document_id",
        )

    return ReanalyzeResponse(
        analysis_id=analysis_id,
        document_id=document_id,
        status="running",
        message="Reanalysis started",
    )
