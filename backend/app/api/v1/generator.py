"""
API router for document generation endpoint.

POST /api/v1/generator/generate — generate a document using AI (GigaChat Pro).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company
from app.database import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
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
    """Generate a document using AI.

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
