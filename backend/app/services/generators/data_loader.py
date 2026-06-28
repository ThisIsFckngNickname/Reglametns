"""
Data loader — loads holding profile, influencing documents, and terms from DB.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException
from app.models.document_term import DocumentTerm
from app.models.company import Company

logger = logging.getLogger(__name__)

_MAX_INFLUENCING_TEXT_CHARS = 10000  # per document


class DataLoader:
    """Loads data from the database for the generation pipeline."""

    async def load_company(self, company_id: int, db: AsyncSession) -> Company:
        """Load company profile by ID."""
        stmt = select(Company).where(Company.id == company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            raise BadRequestException(
                code="COMPANY_NOT_FOUND",
                message="Компания не найдена",
                field="company_id",
            )
        return company

    async def load_influencing_documents(
        self,
        document_ids: Optional[list[int]],
        company_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Load influencing documents with their full text content."""
        if not document_ids:
            return []

        from app.models.document import Document as DocModel

        docs = []
        for doc_id in document_ids:
            stmt = (
                select(DocModel)
                .where(
                    DocModel.id == doc_id,
                    DocModel.company_id == company_id,
                )
                .options(selectinload(DocModel.versions))
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                continue

            # Get latest version with full text
            latest_version = None
            if doc.versions:
                latest_version = max(doc.versions, key=lambda v: v.version_number)

            full_text = ""
            if latest_version and latest_version.full_text:
                full_text = latest_version.full_text[:_MAX_INFLUENCING_TEXT_CHARS]

            entry = {
                "title": doc.title,
                "source": f"Внутренний документ к. {company_id}",
            }
            if full_text:
                entry["full_text"] = full_text

            docs.append(entry)
        return docs

    async def load_company_terms(
        self,
        company_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Load terms and definitions from all documents in the company."""
        from app.models.document import Document as DocModel

        # Get all document IDs for this company
        doc_stmt = select(DocModel.id).where(DocModel.company_id == company_id)
        doc_result = await db.execute(doc_stmt)
        doc_ids = [row[0] for row in doc_result.fetchall()]

        if not doc_ids:
            return []

        # Load all terms
        term_stmt = select(DocumentTerm).where(
            DocumentTerm.document_id.in_(doc_ids)
        )
        term_result = await db.execute(term_stmt)
        terms = term_result.scalars().all()

        # Deduplicate
        seen = set()
        result = []
        for t in terms:
            key = t.term.lower().strip()
            if key not in seen:
                seen.add(key)
                result.append({"term": t.term, "definition": t.definition})
        return result

    # ── V2 (B1): New methods for CompanyTerm / CompanyAbbreviation ──

    async def load_company_terms_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load company-wide terms from CompanyTerm table.

        Returns list of {"term": str, "definition": str}.
        Limited to 50 most relevant terms (alphabetically).
        """
        from app.models.company_term import CompanyTerm

        stmt = select(CompanyTerm).where(
            CompanyTerm.company_id == company_id,
        ).order_by(CompanyTerm.term.asc()).limit(50)

        result = await db.execute(stmt)
        terms = result.scalars().all()

        return [
            {"term": t.term, "definition": t.definition}
            for t in terms
        ]

    async def load_company_abbreviations_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load company-wide abbreviations from CompanyAbbreviation table.

        Returns list of {"abbreviation": str, "full_form": str}.
        Limited to 20 most relevant (alphabetically).
        """
        from app.models.company_abbreviation import CompanyAbbreviation

        stmt = select(CompanyAbbreviation).where(
            CompanyAbbreviation.company_id == company_id,
        ).order_by(CompanyAbbreviation.abbreviation.asc()).limit(20)

        result = await db.execute(stmt)
        abbreviations = result.scalars().all()

        return [
            {"abbreviation": a.abbreviation, "full_form": a.full_form}
            for a in abbreviations
        ]

    async def load_draft_text(self, draft_file_path: str | None) -> str:
        """Load draft text from a file path.

        If path is None, returns empty string.
        Supports .txt and .docx files.
        """
        if not draft_file_path:
            return ""

        import os

        ext = os.path.splitext(draft_file_path)[1].lower()

        try:
            if ext == ".txt":
                with open(draft_file_path, "r", encoding="utf-8") as f:
                    return f.read()
            elif ext == ".docx":
                from docx import Document as DocxDocument
                doc = DocxDocument(draft_file_path)
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            else:
                logger.warning(f"Unsupported draft file type: {ext}")
                return ""
        except Exception as e:
            logger.warning(f"Failed to load draft text from {draft_file_path}: {e}")
            return ""


# Singleton
data_loader = DataLoader()
