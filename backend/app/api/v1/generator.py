"""
API router for document generation endpoint.

POST /api/v1/generator/generate — generate a document using AI (V1, form-data).
POST /api/v1/generator/generate-v2 — generate a document using AI (V2, JSON).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_editor
from app.core.exceptions import ForbiddenException
from app.database import get_db
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.schemas.generator import GenerateRequestV2
from app.services.generator_service import generator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generator", tags=["generator"])


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(
    context: str = Form(..., description="Контекстное описание документа"),
    draft_files: Optional[list[UploadFile]] = File(
        None, description="Черновики (docx/pdf)"
    ),
    influencing_document_ids: Optional[str] = Form(
        None, description="JSON-массив ID документов"
    ),
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Generate a document using AI (V1 — form-data, backward compatible).

    Accepts:
    - context: Text description of what the document should regulate.
    - draft_files: Optional uploaded draft files (.docx, .pdf).
    - influencing_document_ids: Optional JSON array of document IDs
      that should influence the generated document.

    Returns the generated document metadata.
    """
    # Parse influencing_document_ids from JSON string
    ids = []
    if influencing_document_ids:
        try:
            ids = json.loads(influencing_document_ids)
            if not isinstance(ids, list):
                ids = []
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid influencing_document_ids: {influencing_document_ids}")
            ids = []

    logger.info(
        f"Generating document for company {user.active_company_id}, "
        f"context length: {len(context)}, "
        f"drafts: {len(draft_files) if draft_files else 0}, "
        f"influencing docs: {len(ids)}"
    )

    result = await generator_service.generate(
        context_description=context,
        user=user,
        company_id=user.active_company_id,
        draft_files=draft_files,
        influencing_document_ids=ids,
        db=db,
    )
    return result


@router.post("/generate-v2", response_model=DocumentResponse)
async def generate_document_v2(
    request: GenerateRequestV2,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Generate a document using all available knowledge sources (V2).

    Accepts JSON body with:
    - topic: Document topic description (min 20 chars).
    - document_type: Type of document (regulation, order, provision, policy, directive).
    - company_id: Company (holding) ID.
    - draft_file_id: Optional ID of an uploaded draft file.
    - influence_document_ids: Optional list of influencing document IDs.
    - search_enabled: Whether to search the web (default: true).

    Returns the generated document metadata.
    """
    # Verify user belongs to the requested company
    if request.company_id != user.active_company_id:
        raise ForbiddenException(message="Company mismatch")

    # Resolve draft file path if draft_file_id provided
    draft_file_path = None
    if request.draft_file_id:
        draft_file_path = await _resolve_draft_file(
            request.draft_file_id, request.company_id, db
        )

    result = await generator_service.generate_document(
        topic=request.topic,
        company_id=request.company_id,
        document_type=request.document_type,
        user_id=user.id,
        draft_file_path=draft_file_path,
        influence_document_ids=request.influence_document_ids,
        search_enabled=request.search_enabled,
        db=db,
    )
    return result


async def _resolve_draft_file(
    file_id: int, company_id: int, db: AsyncSession
) -> Optional[str]:
    """Resolve draft file ID to file path in storage.

    Loads DocumentVersion by ID, verifies ownership,
    returns the file path on disk.
    """
    from app.models.document import Document as DocModel

    stmt = (
        select(DocumentVersion)
        .join(DocModel, DocumentVersion.document_id == DocModel.id)
        .where(
            DocumentVersion.id == file_id,
            DocModel.company_id == company_id,
        )
    )
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()

    if version and version.file_path:
        return version.file_path

    return None
