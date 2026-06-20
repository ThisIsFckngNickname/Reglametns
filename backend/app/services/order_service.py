"""
Service for order operations.
"""

import logging
import os
from datetime import date
from io import BytesIO
from typing import List, Optional

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import FileTooLarge, InvalidFileType, NotFoundException
from app.models.document import Document
from app.models.order import Order
from app.models.order_document_link import OrderDocumentLink
from app.models.user import User
from app.schemas.orders import (
    OrderDocumentLinkResponse,
    OrderListItem,
    OrderResponse,
    OrderUpdate,
    OrderUploadResponse,
)
from app.services.parser_service import order_parser
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


def _get_file_type(filename: str) -> str:
    """Get file type from filename extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower().replace(".", "")
    if ext in ("docx",):
        return "docx"
    elif ext in ("pdf",):
        return "pdf"
    return ext


def _get_mime_type(file_type: str) -> str:
    """Get MIME type from file type."""
    mimes = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    return mimes.get(file_type, "application/octet-stream")


class OrderService:
    """Service for order operations."""

    async def upload(
        self,
        file: FastAPIUploadFile,
        title: str,
        order_number: Optional[str],
        order_date: Optional[date],
        description: Optional[str],
        holding_id: int,
        user: User,
        db: AsyncSession,
    ) -> OrderUploadResponse:
        """Upload an order file and create an order record."""
        # Validate file
        if not file.filename:
            raise InvalidFileType(message="File has no name")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.allowed_extensions:
            raise InvalidFileType(
                message=f"Invalid file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}"
            )

        content = await file.read()
        file_size = len(content)
        if file_size > settings.max_upload_size:
            raise FileTooLarge(
                message=f"File too large ({file_size} bytes). "
                        f"Maximum is {settings.max_upload_size} bytes"
            )

        file_type = _get_file_type(file.filename)

        # Try to parse order details if not provided
        parsed_number = order_number
        parsed_date = order_date
        if not parsed_number or not parsed_date:
            try:
                # Save to temp location for parsing
                temp_rel_path = await self._save_temp(file.filename, content, holding_id)
                full_path = await storage.get_full_path(temp_rel_path)
                if os.path.exists(full_path):
                    parse_result = order_parser.parse_order_details(full_path, file_type)
                    if not parsed_number and parse_result.order_number:
                        parsed_number = parse_result.order_number
                    if not parsed_date and parse_result.order_date:
                        parsed_date = parse_result.order_date
                    # Clean up temp
                    await storage.delete(temp_rel_path)
            except Exception as e:
                logger.warning(f"Failed to parse order details: {e}")

        # Save file permanently
        # We need a temporary id for file path. Create order first without file_path.
        order = Order(
            holding_id=holding_id,
            title=title,
            order_number=parsed_number,
            order_date=parsed_date,
            description=description,
            status="active",
            created_by=user.id,
        )
        db.add(order)
        await db.flush()
        await db.refresh(order)

        # Save file
        rel_path = await self._save_file(file.filename, content, holding_id, order.id)

        # Update order with file info
        order.file_path = rel_path
        order.file_type = file_type
        order.file_size = file_size
        await db.flush()

        return OrderUploadResponse(
            id=order.id,
            title=order.title,
            order_number=order.order_number,
            order_date=order.order_date,
            status=order.status,
            file_type=file_type,
            file_size=file_size,
        )

    async def _save_temp(self, filename: str, content: bytes, holding_id: int) -> str:
        """Save file to temp location for parsing."""
        from fastapi import UploadFile
        fake_file = UploadFile(filename=filename, file=BytesIO(content))
        # Use a temporary path
        timestamp = int(__import__("time").time())
        temp_path = f"temp/{holding_id}/{timestamp}_{filename}"
        full_dir = os.path.join(settings.storage_path, f"temp/{holding_id}")
        os.makedirs(full_dir, exist_ok=True)
        full_path = os.path.join(settings.storage_path, temp_path)
        with open(full_path, "wb") as f:
            f.write(content)
        return temp_path.replace("\\", "/")

    async def _save_file(
        self, filename: str, content: bytes, holding_id: int, order_id: int
    ) -> str:
        """Save order file to disk."""
        from fastapi import UploadFile
        fake_file = UploadFile(filename=filename, file=BytesIO(content))
        return await storage.save(fake_file, holding_id, order_id, 1)

    async def list_orders(
        self,
        holding_id: int,
        status: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
        db: AsyncSession,
    ) -> dict:
        """List orders with pagination and optional filtering."""
        base_query = select(Order).where(Order.holding_id == holding_id)

        if status:
            base_query = base_query.where(Order.status == status)

        if search:
            pattern = f"%{search}%"
            base_query = base_query.where(
                Order.title.ilike(pattern)
                | Order.order_number.ilike(pattern)
                | Order.description.ilike(pattern)
            )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = (
            base_query
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query)
        orders = result.scalars().all()

        items = [
            OrderListItem(
                id=o.id,
                title=o.title,
                order_number=o.order_number,
                order_date=o.order_date,
                status=o.status,
                file_type=o.file_type,
                file_size=o.file_size,
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
            for o in orders
        ]

        pages = max(1, (total + page_size - 1) // page_size)

        return {
            "items": [item.model_dump() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    async def get_order(self, order_id: int, holding_id: int, db: AsyncSession) -> OrderResponse:
        """Get a single order."""
        order = await self._get_order(order_id, holding_id, db)
        return OrderResponse(
            id=order.id,
            holding_id=order.holding_id,
            title=order.title,
            order_number=order.order_number,
            order_date=order.order_date,
            description=order.description,
            status=order.status,
            file_path=order.file_path,
            file_type=order.file_type,
            file_size=order.file_size,
            created_by=order.created_by,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    async def update_order(
        self, order_id: int, data: OrderUpdate, holding_id: int, db: AsyncSession
    ) -> OrderResponse:
        """Update order metadata."""
        order = await self._get_order(order_id, holding_id, db)

        if data.title is not None:
            order.title = data.title
        if data.order_number is not None:
            order.order_number = data.order_number
        if data.order_date is not None:
            order.order_date = data.order_date
        if data.description is not None:
            order.description = data.description
        if data.status is not None:
            order.status = data.status

        await db.flush()
        return await self.get_order(order_id, holding_id, db)

    async def cancel_order(self, order_id: int, holding_id: int, db: AsyncSession) -> None:
        """Cancel an order (set status to 'cancelled')."""
        order = await self._get_order(order_id, holding_id, db)
        order.status = "cancelled"
        await db.flush()

    async def link_to_document(
        self,
        order_id: int,
        document_id: int,
        link_type: str,
        description: Optional[str],
        holding_id: int,
        db: AsyncSession,
    ) -> OrderDocumentLinkResponse:
        """Link an order to a document."""
        order = await self._get_order(order_id, holding_id, db)

        # Verify document exists and belongs to holding
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Check for duplicate
        stmt = select(OrderDocumentLink).where(
            OrderDocumentLink.order_id == order_id,
            OrderDocumentLink.document_id == document_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            from app.core.exceptions import ConflictException
            raise ConflictException(message="Order is already linked to this document")

        link = OrderDocumentLink(
            order_id=order_id,
            document_id=document_id,
            link_type=link_type,
            description=description,
        )
        db.add(link)
        await db.flush()
        await db.refresh(link)

        return OrderDocumentLinkResponse(
            id=link.id,
            order_id=link.order_id,
            document_id=link.document_id,
            link_type=link.link_type,
            description=link.description,
            created_at=link.created_at,
            document_title=doc.title,
            document_status=doc.status,
        )

    async def unlink_from_document(
        self, link_id: int, holding_id: int, db: AsyncSession
    ) -> None:
        """Remove an order-document link."""
        stmt = select(OrderDocumentLink).where(OrderDocumentLink.id == link_id)
        result = await db.execute(stmt)
        link = result.scalar_one_or_none()

        if link is None:
            raise NotFoundException(message="Link not found", field="link_id")

        # Verify order belongs to holding
        order = await self._get_order(link.order_id, holding_id, db, raise_not_found=False)
        if order is None:
            raise NotFoundException(message="Order not found", field="order_id")

        await db.delete(link)

    async def get_order_documents(
        self, order_id: int, holding_id: int, db: AsyncSession
    ) -> List[OrderDocumentLinkResponse]:
        """Get all documents linked to an order."""
        order = await self._get_order(order_id, holding_id, db)

        links = order.document_links
        result = []
        for link in links:
            doc = None
            if link.document_id:
                stmt = select(Document).where(Document.id == link.document_id)
                r = await db.execute(stmt)
                doc = r.scalar_one_or_none()

            result.append(OrderDocumentLinkResponse(
                id=link.id,
                order_id=link.order_id,
                document_id=link.document_id,
                link_type=link.link_type,
                description=link.description,
                created_at=link.created_at,
                document_title=doc.title if doc else "Unknown",
                document_status=doc.status if doc else None,
            ))

        return result

    async def _get_order(
        self, order_id: int, holding_id: int, db: AsyncSession, raise_not_found: bool = True
    ) -> Optional[Order]:
        """Get order by id and holding_id."""
        stmt = select(Order).where(
            Order.id == order_id,
            Order.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None and raise_not_found:
            raise NotFoundException(message="Order not found", field="order_id")
        return order


# Singleton
order_service = OrderService()
