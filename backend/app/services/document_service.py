"""
Document service — upload, parse, CRUD, and query operations.
"""

import difflib
import logging
import os
from io import BytesIO
from typing import List, Optional

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    FileTooLarge,
    InvalidFileType,
    NotFoundException,
    ParseError,
)
from app.models.document import Document
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_section import DocumentSection
from app.models.document_table import DocumentTable
from app.models.document_term import DocumentTerm
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import (
    DocumentListItem,
    DocumentResponse,
    DocumentUpdate,
    PaginatedResponse,
    UploadResponse,
)
from app.services.parser_service import document_parser, enhanced_document_parser
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


class DocumentService:
    """Service for document operations."""

    async def upload(
        self,
        file: FastAPIUploadFile,
        title: Optional[str],
        description: Optional[str],
        user: User,
        holding_id: int,
        db: AsyncSession,
    ) -> UploadResponse:
        """Upload a file, parse it, and store all extracted data."""
        # Validate file
        if not file.filename:
            raise InvalidFileType(message="File has no name")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.allowed_extensions:
            raise InvalidFileType(
                message=f"Invalid file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}"
            )

        # Check file size
        content = await file.read()
        file_size = len(content)
        if file_size > settings.max_upload_size:
            raise FileTooLarge(
                message=f"File too large ({file_size} bytes). "
                        f"Maximum is {settings.max_upload_size} bytes"
            )

        file_type = _get_file_type(file.filename)

        # Determine title
        doc_title = title
        if not doc_title:
            doc_title = os.path.splitext(file.filename)[0]

        # Create Document record
        document = Document(
            holding_id=holding_id,
            title=doc_title,
            description=description,
            status="draft",
            created_by=user.id,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        # Determine version number
        version_stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document.id
        )
        version_result = await db.execute(version_stmt)
        max_version = version_result.scalar() or 0
        version_number = max_version + 1

        # Save file
        rel_path = await self._save_file(
            file.filename, content, holding_id, document.id, version_number
        )

        # Create DocumentVersion record
        mime_type = _get_mime_type(file_type)
        version = DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            file_path=rel_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=user.id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        # Parse document (use enhanced parser for PDFs)
        try:
            full_path = await storage.get_full_path(rel_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Saved file not found at {full_path}")

            # Use enhanced parser for PDFs to support complex layouts
            parser = enhanced_document_parser if file_type == "pdf" else document_parser
            parse_result = parser.parse(full_path, file_type)
        except Exception as e:
            logger.error(f"Parse error for document {document.id}: {e}", exc_info=True)
            raise ParseError(message=f"Failed to parse document: {str(e)}")
        # Save sections
        section_id_map = {}
        for section_data in parse_result.sections:
            section = DocumentSection(
                document_version_id=version.id,
                parent_id=None,
                title=section_data["title"],
                level=section_data["level"],
                order_num=section_data["order_num"],
                content=section_data.get("content", ""),
            )
            db.add(section)
            await db.flush()
            section_id_map[section_data["order_num"]] = section.id

        # Update parent_id references
        for section_data in parse_result.sections:
            parent_order_num = section_data.get("parent_id")
            if parent_order_num is not None and parent_order_num in section_id_map:
                section_db_id = section_id_map[section_data["order_num"]]
                parent_db_id = section_id_map[parent_order_num]
                stmt = (
                    update(DocumentSection)
                    .where(DocumentSection.id == section_db_id)
                    .values(parent_id=parent_db_id)
                )
                await db.execute(stmt)

        # Save tables
        for table_data in parse_result.tables:
            section_id = None
            sec_order = table_data.get("section_id")
            if sec_order and sec_order in section_id_map:
                section_id = section_id_map[sec_order]

            table = DocumentTable(
                document_version_id=version.id,
                section_id=section_id,
                caption=table_data.get("caption"),
                order_num=table_data["order_num"],
                html_content=table_data["html_content"],
                rows_count=table_data["rows_count"],
                cols_count=table_data["cols_count"],
            )
            db.add(table)

        # Save terms (deduplicated)
        seen_terms = set()
        for term_data in parse_result.terms:
            term_key = term_data["term"].lower().strip()
            if term_key not in seen_terms:
                seen_terms.add(term_key)
                term = DocumentTerm(
                    document_id=document.id,
                    term=term_data["term"],
                    definition=term_data["definition"],
                )
                db.add(term)

        # Save abbreviations (deduplicated)
        seen_abbrs = set()
        for abbr_data in parse_result.abbreviations:
            abbr_key = abbr_data["abbreviation"].lower().strip()
            if abbr_key not in seen_abbrs:
                seen_abbrs.add(abbr_key)
                abbr = DocumentAbbreviation(
                    document_id=document.id,
                    abbreviation=abbr_data["abbreviation"],
                    full_form=abbr_data["full_form"],
                )
                db.add(abbr)

        # Build full_text from all sections
        version.full_text = self._build_full_text(parse_result.sections)

        await db.flush()

        # Store lists in version metadata (as JSON in version_notes if empty)
        if parse_result.lists:
            import json
            # Store lists data in a metadata-like fashion
            # version_notes is nullable Text, use it if it's currently null/empty
            if not version.version_notes:
                version.version_notes = json.dumps(
                    {"lists": parse_result.lists},
                    ensure_ascii=False,
                )

        return UploadResponse(
            id=document.id,
            title=document.title,
            status=document.status,
            file_type=file_type,
            file_size=file_size,
            sections_count=len(parse_result.sections),
            tables_count=len(parse_result.tables),
            terms_count=len(parse_result.terms),
            abbreviations_count=len(parse_result.abbreviations),
            lists_count=len(parse_result.lists),
        )

    async def _save_file(
        self, filename: str, content: bytes, holding_id: int, document_id: int, version_number: int
    ) -> str:
        """Save file bytes to disk using the storage service."""
        fake_file = FastAPIUploadFile(
            filename=filename,
            file=BytesIO(content),
        )
        return await storage.save(fake_file, holding_id, document_id, version_number)

    async def list_documents(
        self,
        holding_id: int,
        status: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
        db: AsyncSession,
    ) -> PaginatedResponse[DocumentListItem]:
        """List documents with pagination and optional filtering."""
        base_query = select(Document).where(Document.holding_id == holding_id)

        if status:
            base_query = base_query.where(Document.status == status)

        if search:
            pattern = f"%{search}%"
            base_query = base_query.where(
                Document.title.ilike(pattern)
                | Document.description.ilike(pattern)
            )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Paginate
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

    async def get_document(self, id: int, holding_id: int, db: AsyncSession) -> DocumentResponse:
        """Get a single document with all metadata."""
        stmt = select(Document).where(
            Document.id == id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        versions_count = len(doc.versions)
        sections_count = 0
        tables_count = 0
        for v in doc.versions:
            sections_count += len(v.sections)
            tables_count += len(v.tables)

        return DocumentResponse(
            id=doc.id,
            holding_id=doc.holding_id,
            title=doc.title,
            description=doc.description,
            status=doc.status,
            created_by=doc.created_by,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            versions_count=versions_count,
            sections_count=sections_count,
            tables_count=tables_count,
            terms_count=len(doc.terms),
            abbreviations_count=len(doc.abbreviations),
        )

    async def update_document(
        self, id: int, data: DocumentUpdate, holding_id: int, db: AsyncSession
    ) -> DocumentResponse:
        """Update document metadata."""
        stmt = select(Document).where(
            Document.id == id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        if data.title is not None:
            doc.title = data.title
        if data.description is not None:
            doc.description = data.description
        if data.status is not None:
            doc.status = data.status

        await db.flush()
        return await self.get_document(id, holding_id, db)

    async def archive_document(self, id: int, holding_id: int, db: AsyncSession) -> None:
        """Archive a document by setting status to 'archived'."""
        stmt = select(Document).where(
            Document.id == id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        doc.status = "archived"
        await db.flush()

    async def get_versions(
        self, document_id: int, holding_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all versions of a document."""
        # Verify ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
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

    async def create_version(
        self,
        document_id: int,
        file: FastAPIUploadFile,
        version_notes: Optional[str],
        user: User,
        holding_id: int,
        db: AsyncSession,
    ) -> dict:
        """Create a new version for an existing document."""
        # Verify document exists and belongs to holding
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

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
        mime_type = _get_mime_type(file_type)

        # Determine version number
        version_stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        version_result = await db.execute(version_stmt)
        max_version = version_result.scalar() or 0
        version_number = max_version + 1

        # Save file
        rel_path = await self._save_file(
            file.filename, content, holding_id, document_id, version_number
        )

        # Create version record
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            file_path=rel_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            version_notes=version_notes,
            uploaded_by=user.id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        # Parse document and save sections + full_text
        try:
            full_path = await storage.get_full_path(rel_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Saved file not found at {full_path}")
            parse_result = document_parser.parse(full_path, file_type)
        except Exception as e:
            logger.error(f"Parse error for version {version.id}: {e}", exc_info=True)
            raise ParseError(message=f"Failed to parse document: {str(e)}")

        # Save sections
        section_id_map = {}
        for section_data in parse_result.sections:
            section = DocumentSection(
                document_version_id=version.id,
                parent_id=None,
                title=section_data["title"],
                level=section_data["level"],
                order_num=section_data["order_num"],
                content=section_data.get("content", ""),
            )
            db.add(section)
            await db.flush()
            section_id_map[section_data["order_num"]] = section.id

        # Update parent_id references
        for section_data in parse_result.sections:
            parent_order_num = section_data.get("parent_id")
            if parent_order_num is not None and parent_order_num in section_id_map:
                section_db_id = section_id_map[section_data["order_num"]]
                parent_db_id = section_id_map[parent_order_num]
                stmt = (
                    update(DocumentSection)
                    .where(DocumentSection.id == section_db_id)
                    .values(parent_id=parent_db_id)
                )
                await db.execute(stmt)

        # Save tables
        for table_data in parse_result.tables:
            section_id = None
            sec_order = table_data.get("section_id")
            if sec_order and sec_order in section_id_map:
                section_id = section_id_map[sec_order]

            table = DocumentTable(
                document_version_id=version.id,
                section_id=section_id,
                caption=table_data.get("caption"),
                order_num=table_data["order_num"],
                html_content=table_data["html_content"],
                rows_count=table_data["rows_count"],
                cols_count=table_data["cols_count"],
            )
            db.add(table)

        # Build full_text from all sections
        version.full_text = self._build_full_text(parse_result.sections)

        # Save terms (deduplicated)
        seen_terms = set()
        for term_data in parse_result.terms:
            term_key = term_data["term"].lower().strip()
            if term_key not in seen_terms:
                seen_terms.add(term_key)
                term = DocumentTerm(
                    document_id=document_id,
                    term=term_data["term"],
                    definition=term_data["definition"],
                )
                db.add(term)

        # Save abbreviations (deduplicated)
        seen_abbrs = set()
        for abbr_data in parse_result.abbreviations:
            abbr_key = abbr_data["abbreviation"].lower().strip()
            if abbr_key not in seen_abbrs:
                seen_abbrs.add(abbr_key)
                abbr = DocumentAbbreviation(
                    document_id=document_id,
                    abbreviation=abbr_data["abbreviation"],
                    full_form=abbr_data["full_form"],
                )
                db.add(abbr)

        await db.flush()

        return {
            "id": version.id,
            "document_id": version.document_id,
            "version_number": version.version_number,
            "file_type": version.file_type,
            "file_size": version.file_size,
            "mime_type": version.mime_type,
            "version_notes": version.version_notes,
            "uploaded_by": version.uploaded_by,
            "created_at": version.created_at,
        }

    async def diff_versions(
        self,
        document_id: int,
        from_version: int,
        to_version: int,
        holding_id: int,
        db: AsyncSession,
    ) -> dict:
        """Compare two versions and return the differences."""
        # Verify document exists
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Get both versions
        v1_stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == from_version,
        )
        v2_stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == to_version,
        )
        v1_result = await db.execute(v1_stmt)
        v2_result = await db.execute(v2_stmt)
        v1 = v1_result.scalar_one_or_none()
        v2 = v2_result.scalar_one_or_none()

        if v1 is None:
            raise NotFoundException(
                message=f"Version {from_version} not found", field="from_version"
            )
        if v2 is None:
            raise NotFoundException(
                message=f"Version {to_version} not found", field="to_version"
            )

        changes = []
        sections_diff = []
        metadata_changes = {}
        full_text_diff = None

        # Detect changes in metadata
        if v1.file_size != v2.file_size:
            changes.append(f"File size changed: {v1.file_size} → {v2.file_size} bytes")
        if v1.file_type != v2.file_type:
            changes.append(f"File type changed: {v1.file_type} → {v2.file_type}")

        # Build sections_diff by comparing sections
        v1_sections_by_id = {s.id: s for s in v1.sections}
        v2_sections_by_id = {s.id: s for s in v2.sections}
        v1_sections_by_title = {s.title: s for s in v1.sections}
        v2_sections_by_title = {s.title: s for s in v2.sections}

        all_section_ids = set(v1_sections_by_id.keys()) | set(v2_sections_by_id.keys())
        all_section_titles = set(v1_sections_by_title.keys()) | set(v2_sections_by_title.keys())

        for title in sorted(all_section_titles, key=lambda t: (
            v1_sections_by_title.get(t, v2_sections_by_title.get(t)).order_num
            if v1_sections_by_title.get(t, v2_sections_by_title.get(t))
            else 0
        )):
            in_v1 = title in v1_sections_by_title
            in_v2 = title in v2_sections_by_title
            s1 = v1_sections_by_title.get(title)
            s2 = v2_sections_by_title.get(title)

            if in_v1 and not in_v2:
                status = "removed"
                changes.append(f"Section removed: {title}")
                sections_diff.append({
                    "section_id": s1.id,
                    "title": title,
                    "status": status,
                })
            elif not in_v1 and in_v2:
                status = "added"
                changes.append(f"Section added: {title}")
                sections_diff.append({
                    "section_id": s2.id,
                    "title": title,
                    "status": status,
                })
            else:
                status = "unchanged"
                # Check if content changed
                if s1 and s2 and s1.content != s2.content:
                    status = "changed"
                    changes.append(f"Section content changed: {title}")
                sections_diff.append({
                    "section_id": s2.id if s2 else s1.id,
                    "title": title,
                    "status": status,
                })

        # Detect table count changes
        if len(v1.tables) != len(v2.tables):
            changes.append(
                f"Table count changed: {len(v1.tables)} → {len(v2.tables)}"
            )

        # Metadata changes for document fields
        metadata_changes = {}
        if doc.title:
            pass  # title is on document, not version

        # Document-level metadata changes (title, status)
        if v1.version_notes != v2.version_notes:
            metadata_changes["version_notes"] = {
                "old": v1.version_notes,
                "new": v2.version_notes,
            }

        # Full text diff using difflib
        text1 = v1.full_text or ""
        text2 = v2.full_text or ""
        if text1 or text2:
            diff_lines = list(difflib.unified_diff(
                text1.splitlines(keepends=True),
                text2.splitlines(keepends=True),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm="",
            ))
            full_text_diff = "".join(diff_lines)

        if not changes:
            changes.append("No significant changes detected between versions")

        return {
            "from_version": {
                "id": v1.id,
                "document_id": v1.document_id,
                "version_number": v1.version_number,
                "file_type": v1.file_type,
                "file_size": v1.file_size,
                "mime_type": v1.mime_type,
                "version_notes": v1.version_notes,
                "uploaded_by": v1.uploaded_by,
                "created_at": v1.created_at,
            },
            "to_version": {
                "id": v2.id,
                "document_id": v2.document_id,
                "version_number": v2.version_number,
                "file_type": v2.file_type,
                "file_size": v2.file_size,
                "mime_type": v2.mime_type,
                "version_notes": v2.version_notes,
                "uploaded_by": v2.uploaded_by,
                "created_at": v2.created_at,
            },
            "changes": changes,
            "sections_diff": sections_diff,
            "metadata_changes": metadata_changes,
            "full_text_diff": full_text_diff,
        }

    async def get_sections_tree(
        self, document_id: int, holding_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get sections as a tree structure from the latest version."""
        # Verify ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
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

    def _build_full_text(self, sections: List[dict]) -> str:
        """Build the full document text from parsed sections."""
        parts = []
        for section in sections:
            title = section.get("title", "")
            content = section.get("content", "")
            if title:
                parts.append(title)
            if content:
                parts.append(content.strip())
        return "\n\n".join(parts)

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
        self, document_id: int, holding_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all terms for a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
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
        self, document_id: int, holding_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all abbreviations for a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
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
        self, document_id: int, holding_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get all tables from the latest version of a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
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


# Singleton
document_service = DocumentService()
