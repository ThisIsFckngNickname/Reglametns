"""
Analysis Pipeline Service — coordinates the 8-step analysis pipeline.

The pipeline runs asynchronously via asyncio.create_task() and manages:
1. extract_text      — get full_text from latest version
2. parse_structure   — count existing sections
3. extract_terms     — extract terms from text
4. extract_abbr      — extract abbreviations from text
5. extract_refs      — count references (MVP: count only)
6. pattern_analysis  — update company profile
7. embedding         — chunk & index in ChromaDB
8. mark_complete     — finalize analysis record
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_version import DocumentVersion
from app.models.document_section import DocumentSection
from app.models.document_term import DocumentTerm
from app.models.document_abbreviation import DocumentAbbreviation

logger = logging.getLogger(__name__)

# ─── Step names ─────────────────────────────────────────────────────────

STEPS = [
    "extract_text",
    "parse_structure",
    "extract_terms",
    "extract_abbr",
    "extract_refs",
    "pattern_analysis",
    "embedding",
    "mark_complete",
]

STEP_TIMEOUTS: dict[str, int] = {
    "extract_text": 5,
    "parse_structure": 30,
    "extract_terms": 30,
    "extract_abbr": 30,
    "extract_refs": 30,
    "pattern_analysis": 30,
    "embedding": 300,
    "mark_complete": 10,
}


def _utcnow_str() -> str:
    """Return ISO 8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(text: str) -> str:
    """Compute SHA256 hex digest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AnalysisPipelineService:
    """Coordinates the 8-step analysis pipeline."""

    async def run(
        self,
        analysis_id: int,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> None:
        """Run the full analysis pipeline in background."""
        # Load the analysis record
        stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
        result = await db.execute(stmt)
        analysis = result.scalar_one_or_none()
        if analysis is None:
            logger.error(f"Analysis record {analysis_id} not found, aborting pipeline")
            return

        # Initialize steps_status
        steps_status: dict[str, dict] = {}
        for step_name in STEPS:
            steps_status[step_name] = {
                "status": "waiting",
                "started_at": None,
                "completed_at": None,
                "error": None,
            }
        analysis.steps_status = steps_status
        await db.flush()

        # Determine if this is a reanalysis (existing data should be deleted)
        is_reanalysis = analysis.file_hash is not None
        if is_reanalysis:
            # Check if there's any existing data worth cleaning
            pass  # handled per-step below

        # ─── Step 1: extract_text ────────────────────────────────────
        file_hash: Optional[str] = None
        full_text: Optional[str] = None
        version_id: Optional[int] = None

        step_result = await self._run_step(
            "extract_text", analysis, self._step_extract_text, db,
            document_id=document_id,
        )
        if step_result and isinstance(step_result, tuple) and len(step_result) == 3:
            file_hash, full_text, version_id = step_result
            if version_id is not None and full_text:
                analysis.document_version_id = version_id
                if file_hash:
                    analysis.file_hash = file_hash
                await db.flush()

        # ─── Step 2: parse_structure ─────────────────────────────────
        sections_count: int = 0
        if version_id is not None:
            sections_count = await self._run_step(
                "parse_structure", analysis, self._step_parse_structure, db,
                version_id=version_id,
            ) or 0

        # ─── Step 3: extract_terms ───────────────────────────────────
        terms_count = await self._run_step(
            "extract_terms", analysis, self._step_extract_terms, db,
            full_text=full_text or "",
            document_id=document_id,
            is_reanalysis=is_reanalysis,
        ) or 0

        # ─── Step 4: extract_abbr ────────────────────────────────────
        abbr_count = await self._run_step(
            "extract_abbr", analysis, self._step_extract_abbr, db,
            full_text=full_text or "",
            document_id=document_id,
            is_reanalysis=is_reanalysis,
        ) or 0

        # ─── Step 5: extract_refs ────────────────────────────────────
        refs_count = await self._run_step(
            "extract_refs", analysis, self._step_extract_refs, db,
            full_text=full_text or "",
        ) or 0

        # ─── Step 6: pattern_analysis ────────────────────────────────
        pattern_result = await self._run_step(
            "pattern_analysis", analysis, self._step_pattern_analysis, db,
            document_id=document_id,
        ) or {}

        # ─── Step 7: embedding ───────────────────────────────────────
        # Reload document to get title
        doc_stmt = select(Document).where(Document.id == document_id)
        doc_result = await db.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        title = doc.title if doc else ""

        chunks_indexed = await self._run_step(
            "embedding", analysis, self._step_embedding, db,
            document_id=document_id,
            company_id=company_id,
            title=title,
            full_text=full_text or "",
            is_reanalysis=is_reanalysis,
        ) or 0

        # ─── Build result_summary ────────────────────────────────────
        final_steps_status = analysis.steps_status or {}
        failed_steps = sum(
            1 for s in final_steps_status.values() if s.get("status") == "error"
        )
        completed_steps = sum(
            1 for s in final_steps_status.values() if s.get("status") == "done"
        )

        result_summary = {
            "sections_found": sections_count,
            "max_depth": 0,
            "terms_found": terms_count,
            "abbreviations_found": abbr_count,
            "references_found": refs_count,
            "chunks_indexed": chunks_indexed,
            "style_analyzed": bool(pattern_result.get("style_extracted"))
            if isinstance(pattern_result, dict)
            else False,
            "total_steps": 8,
            "failed_steps": failed_steps,
            "completed_steps": completed_steps,
        }

        # ─── Step 8: mark_complete ───────────────────────────────────
        await self._run_step(
            "mark_complete", analysis, self._step_mark_complete, db,
            analysis_id=analysis_id,
            file_hash=file_hash or "",
            result_summary=result_summary,
        )

        logger.info(
            f"Pipeline finished for analysis_id={analysis_id}, "
            f"document_id={document_id}: "
            f"completed={completed_steps}/8, failed={failed_steps}"
        )

    async def get_status(
        self,
        analysis_id: int,
        db: AsyncSession,
    ) -> Optional[dict]:
        """Get detailed status of an analysis pipeline run."""
        stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
        result = await db.execute(stmt)
        analysis = result.scalar_one_or_none()
        if analysis is None:
            return None

        return {
            "id": analysis.id,
            "document_id": analysis.document_id,
            "document_version_id": analysis.document_version_id,
            "file_hash": analysis.file_hash,
            "status": analysis.status,
            "steps_status": analysis.steps_status or {},
            "error_message": analysis.error_message,
            "result_summary": analysis.result_summary,
            "created_at": analysis.created_at,
            "completed_at": analysis.completed_at,
        }

    async def get_history(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Get analysis history for a document."""
        stmt = (
            select(DocumentAnalysis)
            .where(DocumentAnalysis.document_id == document_id)
            .order_by(DocumentAnalysis.created_at.desc())
        )
        result = await db.execute(stmt)
        analyses = result.scalars().all()

        return [
            {
                "id": a.id,
                "document_id": a.document_id,
                "document_version_id": a.document_version_id,
                "status": a.status,
                "error_message": a.error_message,
                "result_summary": a.result_summary,
                "created_at": a.created_at,
                "completed_at": a.completed_at,
            }
            for a in analyses
        ]

    async def trigger_analysis(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
        force: bool = False,
    ) -> Optional[int]:
        """Trigger analysis for a document.

        Args:
            document_id: ID of the document.
            company_id: ID of the company.
            db: Database session.
            force: If True, skip idempotency check (for reanalyze).

        Returns:
            analysis_id if analysis was started, None if skipped (idempotency).
        """
        # Load document
        stmt = (
            select(Document)
            .where(Document.id == document_id, Document.company_id == company_id)
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.warning(f"Document {document_id} not found, cannot trigger analysis")
            return None

        # Get latest version
        version_stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        version_result = await db.execute(version_stmt)
        latest_version = version_result.scalar_one_or_none()

        if latest_version is None or not latest_version.full_text:
            logger.warning(
                f"Document {document_id} has no versions with text, "
                "skipping analysis trigger"
            )
            return None

        # Compute current hash
        current_hash = _sha256(latest_version.full_text)

        # Idempotency check (unless forced)
        if not force:
            if doc.analysis_status == "running":
                logger.info(
                    f"Analysis already running for document {document_id}, skipping"
                )
                return None

            if (
                doc.analysis_hash == current_hash
                and doc.analysis_status == "complete"
            ):
                # Дополнительно проверить наличие чанков в ChromaDB
                # (может быть пересборка/очистка ChromaDB)
                from app.services.rag_service import rag_service
                chunks_count = await rag_service.get_document_chunks_count(
                    document_id=document_id,
                    company_id=company_id,
                )
                if chunks_count > 0:
                    logger.info(
                        f"Content unchanged for document {document_id}, "
                        f"ChromaDB has {chunks_count} chunks, "
                        f"skipping analysis (idempotency)"
                    )
                    return None
                else:
                    logger.info(
                        f"Content unchanged but ChromaDB empty for document {document_id}, "
                        f"re-running analysis to restore chunks"
                    )
                    # Продолжаем — запускаем анализ

        # Create DocumentAnalysis record
        analysis = DocumentAnalysis(
            document_id=document_id,
            document_version_id=latest_version.id,
            file_hash=current_hash,
            status="running",
        )
        db.add(analysis)
        await db.flush()

        # Update document status
        doc.analysis_status = "running"
        await db.flush()

        # Launch pipeline in background (creates its own session)
        self._launch_background_pipeline(analysis.id, document_id, company_id)

        logger.info(
            f"Analysis triggered: analysis_id={analysis.id}, document_id={document_id}"
        )
        return analysis.id

    # ─── Private: background launch ──────────────────────────────────

    def _launch_background_pipeline(
        self,
        analysis_id: int,
        document_id: int,
        company_id: int,
    ) -> None:
        """Launch the pipeline in a background asyncio task.

        The pipeline creates its own DB session to avoid depending on
        the HTTP request's session lifecycle.
        """
        import asyncio

        async def _run_in_background():
            try:
                async with async_session() as bg_session:
                    await self.run(
                        analysis_id=analysis_id,
                        document_id=document_id,
                        company_id=company_id,
                        db=bg_session,
                    )
                    await bg_session.commit()
            except Exception as e:
                logger.error(
                    f"Background pipeline crashed for analysis_id={analysis_id}: {e}",
                    exc_info=True,
                )
                # Try to mark as error
                try:
                    async with async_session() as err_session:
                        stmt = select(DocumentAnalysis).where(
                            DocumentAnalysis.id == analysis_id
                        )
                        result = await err_session.execute(stmt)
                        analysis = result.scalar_one_or_none()
                        if analysis:
                            analysis.status = "error"
                            analysis.error_message = (
                                f"Pipeline crashed: {str(e)[:500]}"
                            )
                            analysis.completed_at = datetime.now(
                                timezone.utc
                            ).replace(tzinfo=None)
                        await err_session.commit()
                except Exception as inner_e:
                    logger.error(
                        f"Failed to mark analysis {analysis_id} as error: {inner_e}"
                    )

        asyncio.create_task(_run_in_background())

    # ─── Private: step runner ────────────────────────────────────────

    async def _run_step(
        self,
        step_name: str,
        analysis: DocumentAnalysis,
        func: Any,
        db: AsyncSession,
        **kwargs: Any,
    ) -> Any:
        """Execute a single pipeline step with status tracking.

        Args:
            step_name: Name of the step (key in steps_status).
            analysis: DocumentAnalysis record.
            func: Async callable to execute.
            db: Database session.
            **kwargs: Arguments passed to func.

        Returns:
            Result of func, or None if step failed.
        """
        steps_status = analysis.steps_status or {}
        step_info = steps_status.get(step_name, {})
        if not step_info:
            step_info = {"status": "waiting", "started_at": None, "completed_at": None, "error": None}
        step_info["status"] = "running"
        step_info["started_at"] = _utcnow_str()
        step_info["error"] = None
        steps_status[step_name] = step_info
        analysis.steps_status = steps_status
        await db.flush()

        timeout = STEP_TIMEOUTS.get(step_name, 30)

        try:
            import asyncio

            result = await asyncio.wait_for(
                func(**kwargs),
                timeout=timeout,
            )
            step_info["status"] = "done"
            step_info["completed_at"] = _utcnow_str()
            steps_status[step_name] = step_info
            analysis.steps_status = steps_status
            await db.flush()
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Step {step_name} timed out after {timeout}s")
            step_info["status"] = "error"
            step_info["completed_at"] = _utcnow_str()
            step_info["error"] = f"Step timed out after {timeout}s"
            steps_status[step_name] = step_info
            analysis.steps_status = steps_status
            await db.flush()
            return None
        except Exception as e:
            logger.error(f"Step {step_name} failed: {e}", exc_info=True)
            step_info["status"] = "error"
            step_info["completed_at"] = _utcnow_str()
            step_info["error"] = str(e)[:500]
            steps_status[step_name] = step_info
            analysis.steps_status = steps_status
            await db.flush()
            return None

    # ─── Helpers: sync to company-wide terms ─────────────────────────

    async def _get_document(
        self, document_id: int, db: AsyncSession
    ) -> Optional[Document]:
        """Helper to load a document by ID."""
        stmt = select(Document).where(Document.id == document_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _sync_terms_to_company(
        self,
        company_id: int,
        document_id: int,
        extracted_terms: list[dict],
        db: AsyncSession,
    ) -> dict:
        """Sync extracted terms to company-wide term list.

        Non-blocking: errors are logged but not raised.

        Args:
            company_id: Company ID.
            document_id: Source document ID.
            extracted_terms: List of {"term": str, "definition": str}.
            db: Database session.

        Returns:
            {"inserted": int, "skipped_exists": int, "skipped_mismatch": int}
        """
        from app.models.company_term import CompanyTerm

        stats = {"inserted": 0, "skipped_exists": 0, "skipped_mismatch": 0}

        for term_data in extracted_terms:
            term_name = term_data.get("term", "").strip()
            definition = term_data.get("definition", "").strip()

            if not term_name or not definition:
                continue

            stmt = select(CompanyTerm).where(
                CompanyTerm.company_id == company_id,
                CompanyTerm.term == term_name,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                company_term = CompanyTerm(
                    company_id=company_id,
                    term=term_name,
                    definition=definition,
                    source_document_id=document_id,
                    is_manual=False,
                )
                db.add(company_term)
                stats["inserted"] += 1
            elif existing.definition.strip() != definition:
                logger.info(
                    f"CompanyTerm '{term_name}' exists with different definition. "
                    f"Skipping. DB: '{existing.definition[:50]}', "
                    f"Doc: '{definition[:50]}'"
                )
                stats["skipped_mismatch"] += 1
            else:
                stats["skipped_exists"] += 1

        await db.flush()
        return stats

    async def _sync_abbreviations_to_company(
        self,
        company_id: int,
        document_id: int,
        extracted_abbreviations: list[dict],
        db: AsyncSession,
    ) -> dict:
        """Sync extracted abbreviations to company-wide list.

        Non-blocking: errors are logged but not raised.

        Args:
            company_id: Company ID.
            document_id: Source document ID.
            extracted_abbreviations: List of {"abbreviation": str, "full_form": str}.
            db: Database session.

        Returns:
            {"inserted": int, "skipped_exists": int, "skipped_mismatch": int}
        """
        from app.models.company_abbreviation import CompanyAbbreviation

        stats = {"inserted": 0, "skipped_exists": 0, "skipped_mismatch": 0}

        for abbr_data in extracted_abbreviations:
            abbr = abbr_data.get("abbreviation", "").strip()
            full_form = abbr_data.get("full_form", "").strip()

            if not abbr or not full_form:
                continue

            stmt = select(CompanyAbbreviation).where(
                CompanyAbbreviation.company_id == company_id,
                CompanyAbbreviation.abbreviation == abbr,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                company_abbr = CompanyAbbreviation(
                    company_id=company_id,
                    abbreviation=abbr,
                    full_form=full_form,
                    source_document_id=document_id,
                    is_manual=False,
                )
                db.add(company_abbr)
                stats["inserted"] += 1
            elif existing.full_form.strip() != full_form:
                logger.info(
                    f"CompanyAbbreviation '{abbr}' exists with different full_form. "
                    f"Skipping."
                )
                stats["skipped_mismatch"] += 1
            else:
                stats["skipped_exists"] += 1

        await db.flush()
        return stats

    # ─── Step 1: extract_text ────────────────────────────────────────

    async def _step_extract_text(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """Step 1: Extract full_text from latest version.

        Returns:
            (file_hash, full_text, version_id) or (None, None, None).
        """
        stmt = (
            select(Document)
            .where(Document.id == document_id)
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            return None, None, None

        version_stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        ver_result = await db.execute(version_stmt)
        version = ver_result.scalar_one_or_none()
        if version is None or not version.full_text:
            return None, None, None

        full_text = version.full_text
        version_id = version.id
        file_hash = _sha256(full_text)
        return file_hash, full_text, version_id

    # ─── Step 2: parse_structure ─────────────────────────────────────

    async def _step_parse_structure(
        self,
        version_id: int,
        db: AsyncSession,
    ) -> int:
        """Step 2: Count existing sections for this version."""
        stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_version_id == version_id)
        )
        result = await db.execute(stmt)
        sections = result.scalars().all()
        return len(sections)

    # ─── Step 3: extract_terms ───────────────────────────────────────

    async def _step_extract_terms(
        self,
        full_text: str,
        document_id: int,
        is_reanalysis: bool,
        db: AsyncSession,
    ) -> int:
        """Step 3: Extract terms and definitions."""
        from app.parsers.helpers import _extract_terms_from_text

        if is_reanalysis:
            await db.execute(
                delete(DocumentTerm).where(DocumentTerm.document_id == document_id)
            )

        terms = _extract_terms_from_text(full_text)
        for term_data in terms:
            term = DocumentTerm(
                document_id=document_id,
                term=term_data.get("term", ""),
                definition=term_data.get("definition", ""),
            )
            db.add(term)
        await db.flush()

        # NEW: Sync to company-wide terms (non-blocking)
        doc = await self._get_document(document_id, db)
        if doc:
            try:
                sync_stats = await self._sync_terms_to_company(
                    company_id=doc.company_id,
                    document_id=document_id,
                    extracted_terms=terms,
                    db=db,
                )
                logger.info(f"CompanyTerm sync: {sync_stats}")
            except Exception as e:
                logger.warning(f"CompanyTerm sync failed (non-blocking): {e}")

        return len(terms)

    # ─── Step 4: extract_abbr ────────────────────────────────────────

    async def _step_extract_abbr(
        self,
        full_text: str,
        document_id: int,
        is_reanalysis: bool,
        db: AsyncSession,
    ) -> int:
        """Step 4: Extract abbreviations."""
        from app.parsers.helpers import _extract_abbreviations_from_text

        if is_reanalysis:
            await db.execute(
                delete(DocumentAbbreviation).where(
                    DocumentAbbreviation.document_id == document_id
                )
            )

        abbrs = _extract_abbreviations_from_text(full_text)
        for abbr_data in abbrs:
            abbr = DocumentAbbreviation(
                document_id=document_id,
                abbreviation=abbr_data.get("abbreviation", ""),
                full_form=abbr_data.get("full_form", ""),
            )
            db.add(abbr)
        await db.flush()

        # NEW: Sync to company-wide abbreviations (non-blocking)
        doc = await self._get_document(document_id, db)
        if doc:
            try:
                sync_stats = await self._sync_abbreviations_to_company(
                    company_id=doc.company_id,
                    document_id=document_id,
                    extracted_abbreviations=abbrs,
                    db=db,
                )
                logger.info(f"CompanyAbbreviation sync: {sync_stats}")
            except Exception as e:
                logger.warning(f"CompanyAbbreviation sync failed (non-blocking): {e}")

        return len(abbrs)

    # ─── Step 5: extract_refs ────────────────────────────────────────

    async def _step_extract_refs(
        self,
        full_text: str,
    ) -> int:
        """Step 5: Count references (MVP: count only, no storage)."""
        count = 0
        count += len(re.findall(
            r"(?:Регламент|ФЗ|Приказ|Постановление|Распоряжение)\s*№\s*[\d\-]+",
            full_text,
        ))
        count += len(re.findall(r"https?://[^\s]+", full_text))
        return count

    # ─── Step 6: pattern_analysis ────────────────────────────────────

    async def _step_pattern_analysis(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> dict:
        """Step 6: Analyze document patterns (no was_analyzed check)."""
        from app.services.pattern_analysis_service import pattern_analysis_service

        return await pattern_analysis_service.analyze_document_patterns(
            document_id=document_id,
            db=db,
        )

    # ─── Step 7: embedding ───────────────────────────────────────────

    async def _step_embedding(
        self,
        document_id: int,
        company_id: int,
        title: str,
        full_text: str,
        is_reanalysis: bool,
    ) -> int:
        """Step 7: Chunk, embed, and index in ChromaDB."""
        from app.services.rag_service import rag_service

        if is_reanalysis:
            try:
                await rag_service.delete_document_chunks(
                    document_id=document_id,
                    company_id=company_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete old chunks for document {document_id}: {e}"
                )

        try:
            chunks_count = await rag_service.index_document(
                document_id=document_id,
                company_id=company_id,
                title=title,
                full_text=full_text,
            )
            return chunks_count
        except Exception as e:
            logger.error(f"Embedding step failed for document {document_id}: {e}")
            return 0

    # ─── Step 8: mark_complete ───────────────────────────────────────

    async def _step_mark_complete(
        self,
        analysis_id: int,
        file_hash: str,
        result_summary: dict,
        db: AsyncSession,
    ) -> None:
        """Step 8: Finalize analysis record."""
        stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
        result = await db.execute(stmt)
        analysis = result.scalar_one_or_none()
        if analysis is None:
            logger.error(f"Analysis {analysis_id} not found in mark_complete")
            return

        steps_status = analysis.steps_status or {}

        # Determine final status
        if not steps_status:
            analysis.status = "complete"
        elif all(
            s.get("status") == "error" for s in steps_status.values()
        ):
            analysis.status = "error"
            analysis.error_message = "All pipeline steps failed"
        else:
            analysis.status = "complete"

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        analysis.completed_at = now
        analysis.result_summary = result_summary
        analysis.steps_status = steps_status
        await db.flush()

        # Update Document
        doc_stmt = select(Document).where(Document.id == analysis.document_id)
        doc_result = await db.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.analysis_hash = file_hash or None
            doc.analysis_status = analysis.status

        await db.flush()


# Singleton
analysis_pipeline_service = AnalysisPipelineService()
