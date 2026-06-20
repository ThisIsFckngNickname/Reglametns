"""
API router for order endpoints.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_holding
from app.database import get_db
from app.models.user import User
from app.schemas.orders import (
    OrderDocumentLinkResponse,
    OrderLinkDocumentRequest,
    OrderListItem,
    OrderResponse,
    OrderUpdate,
    OrderUploadResponse,
)
from app.services.order_service import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/upload", response_model=OrderUploadResponse, status_code=201)
async def upload_order(
    file: UploadFile = File(...),
    title: str = Form(...),
    order_number: Optional[str] = Form(None),
    order_date: Optional[date] = Form(None),
    description: Optional[str] = Form(None),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Upload an order file and create an order record."""
    return await order_service.upload(
        file=file,
        title=title,
        order_number=order_number,
        order_date=order_date,
        description=description,
        holding_id=user.active_holding_id,
        user=user,
        db=db,
    )


@router.get("")
async def list_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/number/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """List orders with pagination and optional filtering."""
    return await order_service.list_orders(
        holding_id=user.active_holding_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get order details."""
    return await order_service.get_order(
        order_id=order_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    body: OrderUpdate,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Update order metadata."""
    return await order_service.update_order(
        order_id=order_id,
        data=body,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.delete("/{order_id}", status_code=204)
async def cancel_order(
    order_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an order (set status to 'cancelled')."""
    await order_service.cancel_order(
        order_id=order_id,
        holding_id=user.active_holding_id,
        db=db,
    )
    return Response(status_code=204)


@router.get("/{order_id}/documents", response_model=List[OrderDocumentLinkResponse])
async def get_order_documents(
    order_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Get all documents linked to this order."""
    return await order_service.get_order_documents(
        order_id=order_id,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.post("/{order_id}/documents", response_model=OrderDocumentLinkResponse, status_code=201)
async def link_order_to_document(
    order_id: int,
    body: OrderLinkDocumentRequest,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Link this order to a document."""
    return await order_service.link_to_document(
        order_id=order_id,
        document_id=body.document_id,
        link_type=body.link_type,
        description=body.description,
        holding_id=user.active_holding_id,
        db=db,
    )


@router.delete("/{order_id}/documents/{link_id}", status_code=204)
async def unlink_order_from_document(
    order_id: int,
    link_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """Remove an order-document link."""
    await order_service.unlink_from_document(
        link_id=link_id,
        holding_id=user.active_holding_id,
        db=db,
    )
    return Response(status_code=204)
