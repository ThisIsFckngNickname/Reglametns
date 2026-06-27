"""
Document read service — query and retrieval operations.
"""

import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.document_version import DocumentVersion
from app.schemas.document import (
    DocumentListItem,
    DocumentResponse,
    PaginatedResponse,
)

logger = logging.getLogger(__name__)


class DocumentReadService:
    """Read-only document queries."""

    async def list_documents(
        self,
        company_id: int,
        status: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
        db: AsyncSession,
    ) -> PaginatedResponse[DocumentListItem]:
        """List documents with pagination and optional filtering."""
        base_query = select(Document).where(Document.company_id == company_id)

        if status:
            base_query = base_query.where(Document.status == status)

        # NOTE: We do NOT apply search via SQL ilike() because SQLite's
        # LOWER() doesn't handle Cyrillic/Unicode. Instead we fetch the
        # page, filter in Python (which handles Unicode correctly), and
        # re-fetch with adjusted offset if needed.
        # This works efficiently for typical document counts (< 10000).

        if search:
            search_lower = search.lower()
            # Fetch matching IDs by loading ALL docs for this company
            all_stmt = select(Document).where(Document.company_id == company_id)
            if status:
                all_stmt = all_stmt.where(Document.status == status)
            all_result = await db.execute(all_stmt)
            all_docs = all_result.scalars().all()

            # Python-side Unicode-safe filtering
            matching_ids = []
            for d in all_docs:
                if search_lower in (d.title or '').lower() or \
                   (d.description and search_lower in d.description.lower()):
                    matching_ids.append(d.id)

            total = len(matching_ids)

            # Paginate the matching IDs
            offset = (page - 1) * page_size
            page_ids = matching_ids[offset:offset + page_size]

            if page_ids:
                from sqlalchemy import case as sqlalchemy_case
                # Preserve order from matching_ids
                ordering = sqlalchemy_case(
                    {Document.id == id_: idx for idx, id_ in enumerate(page_ids)},
                    value=None,
                )
                query = (
                    select(Document)
                    .where(Document.id.in_(page_ids))
                    .order_by(ordering)
                )
                result = await db.execute(query)
                documents = result.scalars().all()
            else:
                documents = []
        else:
            # No search: normal pagination
            count_query = select(func.count()).select_from(base_query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            query = (
                base_query
                .order_by(Document.updated_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await db.execute(query)
            documents = result.scalars().all()

        items = []
        for doc in documents:
            latest_ver = (
                await db.execute(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == doc.id)
                    .order_by(DocumentVersion.version_number.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            items.append(DocumentListItem(
                id=doc.id,
                title=doc.title,
                description=doc.description,
                status=doc.status,
                was_analyzed=doc.was_analyzed,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                file_type=latest_ver.file_type if latest_ver else None,
                file_size=latest_ver.file_size if latest_ver else None,
                version_number=latest_ver.version_number if latest_ver else None,
            ))

        pages = max(1, (total + page_size - 1) // page_size)

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_document(self, id: int, company_id: int, db: AsyncSession) -> DocumentResponse:
        """Get a single document with all metadata."""
        stmt = (
            select(Document)
            .where(Document.id == id, Document.company_id == company_id)
            .options(
                selectinload(Document.versions)
                .selectinload(DocumentVersion.sections),
                selectinload(Document.versions)
                .selectinload(DocumentVersion.tables),
                selectinload(Document.terms),
                selectinload(Document.abbreviations),
                selectinload(Document.creator),
            )
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Compute stats
        versions_count = len(doc.versions)
        sections_count = 0
        tables_count = 0
        for v in doc.versions:
            sections_count += len(v.sections)
            tables_count += len(v.tables)

        # Find the latest version (highest version_number)
        latest_version = None
        if doc.versions:
            latest_version = max(doc.versions, key=lambda v: v.version_number)

        # Build creator info
        creator_info = None
        if doc.creator:
            creator_info = {"id": doc.creator.id, "email": doc.creator.email}

        # Build current_version brief
        current_version_brief = None
        if latest_version:
            current_version_brief = {
                "id": latest_version.id,
                "version_number": latest_version.version_number,
                "file_type": latest_version.file_type,
                "file_size": latest_version.file_size,
                "created_at": latest_version.created_at,
            }

        return DocumentResponse(
            id=doc.id,
            company_id=doc.company_id,
            title=doc.title,
            description=doc.description,
            status=doc.status,
            created_by=creator_info,
            current_version=current_version_brief,
            stats={
                "sections_count": sections_count,
                "tables_count": tables_count,
                "terms_count": len(doc.terms),
                "abbreviations_count": len(doc.abbreviations),
                "versions_count": versions_count,
            },
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    async def get_versions(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all versions of a document."""
        # Verify ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        ver_stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        ver_result = await db.execute(ver_stmt)
        versions = ver_result.scalars().all()

        return [
            {
                "id": v.id,
                "document_id": v.document_id,
                "version_number": v.version_number,
                "file_type": v.file_type,
                "file_size": v.file_size,
                "mime_type": v.mime_type,
                "version_notes": v.version_notes,
                "uploaded_by": v.uploaded_by,
                "created_at": v.created_at,
            }
            for v in versions
        ]

    async def get_sections_tree(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get sections as a tree structure from the latest version."""
        # Verify ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Latest version
        ver_stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        ver_result = await db.execute(ver_stmt)
        version = ver_result.scalar_one_or_none()

        if version is None:
            return []

        sections_stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_version_id == version.id)
            .order_by(DocumentSection.order_num)
        )
        sections_result = await db.execute(sections_stmt)
        sections = sections_result.scalars().all()

        return self._build_section_tree(list(sections))

    def _build_section_tree(
        self, sections: List[DocumentSection], parent_id: Optional[int] = None
    ) -> List[dict]:
        """Recursively build a section tree."""
        tree = []
        for section in sections:
            if section.parent_id == parent_id:
                children = self._build_section_tree(sections, section.id)
                tree.append({
                    "id": section.id,
                    "document_version_id": section.document_version_id,
                    "parent_id": section.parent_id,
                    "title": section.title,
                    "level": section.level,
                    "order_num": section.order_num,
                    "content": section.content,
                    "children": children,
                })
        return tree

    async def get_terms(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all terms for a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        return [
            {"id": t.id, "document_id": t.document_id, "term": t.term, "definition": t.definition}
            for t in doc.terms
        ]

    async def get_abbreviations(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all abbreviations for a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        return [
            {
                "id": a.id,
                "document_id": a.document_id,
                "abbreviation": a.abbreviation,
                "full_form": a.full_form,
            }
            for a in doc.abbreviations
        ]

    async def get_tables(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all tables from the latest version of a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        ver_stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        ver_result = await db.execute(ver_stmt)
        version = ver_result.scalar_one_or_none()

        if version is None:
            return []

        return [
            {
                "id": t.id,
                "document_version_id": t.document_version_id,
                "section_id": t.section_id,
                "caption": t.caption,
                "order_num": t.order_num,
                "html_content": t.html_content,
                "rows_count": t.rows_count,
                "cols_count": t.cols_count,
            }
            for t in version.tables
        ]

    async def _verify_ownership(
        self, document_id: int, company_id: int, db: AsyncSession
    ):
        """Verify that a document belongs to the given company.
        
        Returns the Document if found, None otherwise.
        """
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_outgoing_links(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get outgoing links from a document with target document info."""
        from app.models.document_link import DocumentLink

        # Verify ownership
        doc = await self._verify_ownership(document_id, company_id, db)
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        stmt = (
            select(DocumentLink)
            .where(DocumentLink.source_document_id == document_id)
            .join(Document, DocumentLink.target_document_id == Document.id)
            .add_columns(
                Document.title.label("target_title"),
                Document.status.label("target_status"),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row[0].id,
                "source_document_id": row[0].source_document_id,
                "target_document_id": row[0].target_document_id,
                "link_type": row[0].link_type,
                "is_manual": row[0].is_manual,
                "description": row[0].description,
                "created_by": row[0].created_by,
                "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
                "target_title": row[1],
                "target_status": row[2],
            }
            for row in rows
        ]

    async def get_incoming_links(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get incoming links to a document with source document info."""
        from app.models.document_link import DocumentLink

        # Verify ownership
        doc = await self._verify_ownership(document_id, company_id, db)
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        stmt = (
            select(DocumentLink)
            .where(DocumentLink.target_document_id == document_id)
            .join(Document, DocumentLink.source_document_id == Document.id)
            .add_columns(
                Document.title.label("source_title"),
                Document.status.label("source_status"),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row[0].id,
                "source_document_id": row[0].source_document_id,
                "target_document_id": row[0].target_document_id,
                "link_type": row[0].link_type,
                "is_manual": row[0].is_manual,
                "description": row[0].description,
                "created_by": row[0].created_by,
                "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
                "source_title": row[1],
                "source_status": row[2],
            }
            for row in rows
        ]
