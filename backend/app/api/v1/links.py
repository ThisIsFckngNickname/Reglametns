"""
API router for document link endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_holding
from app.database import get_db
from app.models.user import User
from app.schemas.links import DocumentLinkCreate, DocumentLinkSourceResponse
from app.services.link_service import link_service

router = APIRouter(prefix="/documents/{document_id}/links", tags=["links"])


@router.get("", response_model=List[DocumentLinkSourceResponse])
async def list_links(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """List all links (source + target) for a document."""
    return await link_service.list_links(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.post("", response_model=DocumentLinkSourceResponse, status_code=201)
async def create_link(
    document_id: int,
    body: DocumentLinkCreate,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Create a manual link from this document to another."""
    return await link_service.create_link(
        source_document_id=document_id,
        body=body,
        user_id=user.id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.delete("/{link_id}", status_code=204)
async def delete_link(
    document_id: int,
    link_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document link."""
    await link_service.delete_link(
        link_id=link_id,
        user_id=user.id,
        holding_id=user.active_holding_id,
        db=db,
    )
    return Response(status_code=204)
