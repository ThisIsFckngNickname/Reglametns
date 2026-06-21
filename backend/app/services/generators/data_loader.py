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


# Singleton
data_loader = DataLoader()
