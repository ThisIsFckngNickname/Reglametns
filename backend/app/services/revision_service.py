"""
Revision service — orchestrates document revision via LLM.

Flow:
1. Verify document exists and is not archived
2. Get current text from latest DocumentVersion
3. Build revision prompt with comment + optional target section
4. Call LLM (Ollama) with low temperature for precise edits
5. Generate diff and detect real changes
6. Create new version with revised text (Phase 7)
7. Log revision in DocumentRevision table
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.user import User
from app.schemas.revision import (
    DiffResult,
    DiffStats,
    ReviseRequest,
    ReviseResponse,
    RevisionDetail,
    RevisionHistoryItem,
)
from app.services.diff_service import diff_service
from app.services.ollama_client import ollama_client
from app.services.storage_service import storage
from app.services.version_service import version_service

logger = logging.getLogger(__name__)

REVISION_SYSTEM_PROMPT = """Ты — юрист холдинга. Внеси правки в документ в соответствии с замечаниями пользователя. Сохрани структуру, стиль, нумерацию разделов и общую логику документа. Ответь ПОЛНЫМ ТЕКСТОМ документа целиком, а не только изменениями.

Правила:
1. Сохраняй структуру документа (разделы, подразделы, нумерацию).
2. Вноси изменения только в соответствии с замечанием.
3. Если указан целевой раздел — меняй только его.
4. Если замечание противоречит содержанию документа — уточни в начале ответа в скобках.
5. Не добавляй markdown-разметку, ответ должен быть чистым текстом."""


class RevisionService:
    """Service for revising documents via LLM."""

    def __init__(self, llm_client=None, diff_svc=None):
        self._llm_client = llm_client or ollama_client
        self._diff_svc = diff_svc or diff_service

    async def revise_document(
        self,
        document_id: int,
        comment: str,
        target_section: Optional[str],
        current_user: User,
        db: AsyncSession,
    ) -> ReviseResponse:
        """Revise a document based on user feedback.

        Args:
            document_id: ID of the document to revise.
            comment: User's change request.
            target_section: Optional section to target.
            current_user: User making the request.
            db: Database session.

        Returns:
            ReviseResponse with diff and revision details.

        Raises:
            NotFoundException: Document not found.
            BadRequestException: Document is archived or has no content.
            RuntimeError: LLM call failed.
        """
        # 1. Verify document exists and is not archived
        doc = await self._get_document(document_id, current_user.active_company_id, db)
        if doc.status == "archived":
            raise BadRequestException(
                code="DOCUMENT_ARCHIVED",
                message="Cannot revise an archived document",
            )

        # 2. Get current text
        old_text = await self._get_document_text(doc)
        if not old_text or not old_text.strip():
            raise BadRequestException(
                code="NO_CONTENT",
                message="Document has no text content",
            )

        # 3. Build prompt
        user_prompt = self._build_revision_prompt(old_text, comment, target_section)

        # 4. Call LLM
        try:
            new_text = await self._llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": REVISION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=32000,
            )
        except Exception as e:
            logger.error(f"LLM call failed during revision: {e}")
            raise RuntimeError(f"LLM call failed: {e}")

        if not new_text or not new_text.strip():
            raise RuntimeError("LLM returned empty response")

        # 5. Clean LLM response (strip markdown code fences if present)
        new_text = self._clean_llm_response(new_text)

        # 6. Generate diff
        diff_result = self._diff_svc.generate_diff(old_text, new_text)

        # 7. Check if anything changed
        if diff_result.stats.added == 0 and diff_result.stats.removed == 0 and diff_result.stats.changed == 0:
            return ReviseResponse(
                document_id=document_id,
                old_text=old_text,
                new_text=old_text,
                diff=diff_result,
                revision_id=None,
                changed=False,
            )

        # 8. Save new text — create new version (Phase 7)
        await self._save_document_text(doc, new_text, db)

        # 9. Log revision
        revision = DocumentRevision(
            document_id=document_id,
            comment=comment,
            target_section=target_section,
            old_text=old_text,
            new_text=new_text,
            stats_json={
                "added": diff_result.stats.added,
                "removed": diff_result.stats.removed,
                "changed": diff_result.stats.changed,
            },
            created_by=current_user.id,
        )
        db.add(revision)
        await db.flush()
        await db.refresh(revision)

        logger.info(
            f"Document {document_id} revised: revision_id={revision.id}, "
            f"added={diff_result.stats.added}, removed={diff_result.stats.removed}"
        )

        return ReviseResponse(
            document_id=document_id,
            old_text=old_text,
            new_text=new_text,
            diff=diff_result,
            revision_id=revision.id,
            changed=True,
        )

    async def get_revision_history(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> list[RevisionHistoryItem]:
        """Get revision history for a document.

        Args:
            document_id: ID of the document.
            company_id: Company ID for access control.
            db: Database session.

        Returns:
            List of RevisionHistoryItem, newest first.
        """
        doc = await self._get_document(document_id, company_id, db)

        stmt = (
            select(DocumentRevision)
            .where(DocumentRevision.document_id == document_id)
            .order_by(DocumentRevision.created_at.desc())
        )
        result = await db.execute(stmt)
        revisions = result.scalars().all()

        items = []
        for rev in revisions:
            stats = None
            if rev.stats_json:
                stats = DiffStats(
                    added=rev.stats_json.get("added", 0),
                    removed=rev.stats_json.get("removed", 0),
                    changed=rev.stats_json.get("changed", 0),
                )

            items.append(RevisionHistoryItem(
                id=rev.id,
                comment=rev.comment,
                target_section=rev.target_section,
                stats=stats,
                created_by_email=rev.author.email if rev.author else None,
                created_at=rev.created_at,
            ))

        return items

    async def get_revision_detail(
        self,
        document_id: int,
        revision_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> RevisionDetail:
        """Get details of a specific revision.

        Args:
            document_id: ID of the document.
            revision_id: ID of the revision.
            company_id: Company ID for access control.
            db: Database session.

        Returns:
            RevisionDetail with full text if available.

        Raises:
            NotFoundException: Document or revision not found.
        """
        doc = await self._get_document(document_id, company_id, db)

        stmt = select(DocumentRevision).where(
            DocumentRevision.id == revision_id,
            DocumentRevision.document_id == document_id,
        )
        result = await db.execute(stmt)
        revision = result.scalar_one_or_none()

        if revision is None:
            raise NotFoundException(
                message="Revision not found",
                field="revision_id",
            )

        stats = None
        if revision.stats_json:
            stats = DiffStats(
                added=revision.stats_json.get("added", 0),
                removed=revision.stats_json.get("removed", 0),
                changed=revision.stats_json.get("changed", 0),
            )

        return RevisionDetail(
            id=revision.id,
            document_id=revision.document_id,
            comment=revision.comment,
            target_section=revision.target_section,
            stats=stats,
            created_by_email=revision.author.email if revision.author else None,
            created_at=revision.created_at,
            old_text=revision.old_text,
            new_text=revision.new_text,
        )

    async def get_revision_diff(
        self,
        document_id: int,
        revision_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> dict:
        """Get diff for a specific revision (old vs new text stored in revision).

        Args:
            document_id: ID of the document.
            revision_id: ID of the revision.
            company_id: Company ID for access control.
            db: Database session.

        Returns:
            Dict with old_text, new_text, and diff.

        Raises:
            NotFoundException: Document or revision not found.
            BadRequestException: Revision text not available.
        """
        doc = await self._get_document(document_id, company_id, db)

        stmt = select(DocumentRevision).where(
            DocumentRevision.id == revision_id,
            DocumentRevision.document_id == document_id,
        )
        result = await db.execute(stmt)
        revision = result.scalar_one_or_none()

        if revision is None:
            raise NotFoundException(
                message="Revision not found",
                field="revision_id",
            )

        if not revision.old_text or not revision.new_text:
            raise BadRequestException(
                message="Revision text not available (old_text/new_text not stored)",
            )

        diff_result = self._diff_svc.generate_diff(revision.old_text, revision.new_text)

        return {
            "old_text": revision.old_text,
            "new_text": revision.new_text,
            "diff": diff_result,
        }

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_document(self, document_id: int, company_id: int, db: AsyncSession) -> Document:
        """Verify document exists and belongs to the user's company."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(
                message="Document not found",
                field="document_id",
            )
        return doc

    async def _get_document_text(self, doc: Document) -> str:
        """Get the full text of a document from the latest version's full_text."""
        if not doc.versions:
            return ""

        latest = max(doc.versions, key=lambda v: v.version_number)

        if latest.full_text:
            return latest.full_text

        # Fall back to reading file + extracting text
        try:
            file_bytes = await storage.get(latest.file_path)
            from app.services.parser_service import parser_service
            text = await parser_service.extract_text(file_bytes, latest.file_type)
            return text or ""
        except Exception as e:
            logger.warning(f"Failed to extract text from file: {e}")
            return ""

    async def _save_document_text(self, doc: Document, new_text: str, db: AsyncSession) -> None:
        """Create a new version with the revised text (Phase 7).

        Instead of overwriting full_text on the latest version,
        this creates a new DocumentVersion with the revised content.
        The new version gets version_number = max + 1.
        """
        # Create a new docx from the revised text in memory
        from io import BytesIO
        from docx import Document as DocxDocument

        docx = DocxDocument()
        for paragraph in new_text.split("\n"):
            if paragraph.strip():
                docx.add_paragraph(paragraph)

        file_io = BytesIO()
        docx.save(file_io)
        file_content = file_io.getvalue()

        # Create new version
        filename = "revised_document.docx"
        comment = "Ревизия документа"

        new_version = await version_service.create_version(
            document_id=doc.id,
            company_id=doc.company_id,
            file_content=file_content,
            filename=filename,
            author_id=doc.created_by or 0,
            comment=comment,
            db=db,
        )

        # Set full_text on the new version for immediate access
        new_version.full_text = new_text
        await db.flush()

        logger.info(
            f"Created new version {new_version.version_number} for "
            f"document {doc.id} after revision"
        )

    def _build_revision_prompt(
        self,
        old_text: str,
        comment: str,
        target_section: Optional[str],
    ) -> str:
        """Build the revision prompt for LLM."""
        parts = ["Исходный текст документа:\n", old_text, "\n\n"]

        parts.append("Замечание пользователя:\n")
        parts.append(comment)

        if target_section:
            parts.append(f"\n\nЦелевой раздел: {target_section}")
            parts.append(
                "\n\nВнеси правки только в указанный раздел. "
                "Остальные разделы оставь без изменений."
            )

        parts.append("\n\nВерни ПОЛНЫЙ текст документа целиком с внесёнными правками.")

        return "".join(parts)

    def _clean_llm_response(self, text: str) -> str:
        """Strip markdown code fences that LLM might add."""
        text = text.strip()
        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            else:
                text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# Singleton
revision_service = RevisionService()
