"""
Document Saver Service — handles saving generated documents to DB and storage.

Extracted from duplicated save logic in GeneratorService.generate()
and GeneratorService.generate_mock().
"""

import logging
import os
from io import BytesIO

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_status import DocumentStatus
from app.models.document_term import DocumentTerm
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentVersionBrief
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


class DocumentSaver:
    """Saves generated documents to DB and storage.

    Encapsulates the common save pipeline:
    1. Create Document record
    2. Read generated .docx file
    3. Save file to storage
    4. Create DocumentVersion record
    5. Save terms and abbreviations
    6. Build and return DocumentResponse
    """

    async def save_generated_document(
        self,
        company_id: int,
        doc_title: str,
        description: str,
        output_path: str,
        sections_count: int,
        terms: list[dict],
        abbreviations: list[dict],
        user: User,
        db: AsyncSession,
    ) -> DocumentResponse:
        """Save a generated document to DB and storage.

        Args:
            company_id: Company ID.
            doc_title: Document title.
            description: Document description.
            output_path: Path to the generated .docx file.
            sections_count: Number of sections in the generated document.
            terms: List of term-definition dicts.
            abbreviations: List of abbreviation-full_form dicts.
            user: The creating user.
            db: Database session.

        Returns:
            DocumentResponse with saved document details.
        """
        # 1. Create Document record
        document = Document(
            company_id=company_id,
            title=doc_title,
            description=description,
            status=DocumentStatus.DRAFT,
            created_by=user.id,
        )
        db.add(document)
        await db.flush()

        # 2. Read file content
        with open(output_path, "rb") as f:
            file_content = f.read()

        # 3. Save to storage
        fake_file = FastAPIUploadFile(
            filename=os.path.basename(output_path),
            file=BytesIO(file_content),
        )
        rel_path = await storage.save(fake_file, company_id, document.id, 1)

        # 4. Create DocumentVersion
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            file_path=rel_path,
            file_type="docx",
            file_size=len(file_content),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            uploaded_by=user.id,
        )
        db.add(version)

        # 5. Save terms
        for term_item in terms:
            term = DocumentTerm(
                document_id=document.id,
                term=term_item.get("term", ""),
                definition=term_item.get("definition", ""),
            )
            db.add(term)

        # 6. Save abbreviations
        for abbr_item in abbreviations:
            abbr = DocumentAbbreviation(
                document_id=document.id,
                abbreviation=abbr_item.get("abbreviation", ""),
                full_form=abbr_item.get("full_form", ""),
            )
            db.add(abbr)

        await db.flush()

        # 7. Build response
        current_version_brief = DocumentVersionBrief(
            id=version.id,
            version_number=version.version_number,
            file_type=version.file_type,
            file_size=version.file_size,
            created_at=version.created_at,
        )

        return DocumentResponse(
            id=document.id,
            company_id=company_id,
            title=doc_title,
            description=description,
            status=DocumentStatus.DRAFT,
            current_version=current_version_brief,
            created_by={"id": user.id, "email": user.email},
            created_at=document.created_at,
            updated_at=document.updated_at,
            stats={
                "versions_count": 1,
                "sections_count": sections_count,
                "tables_count": 0,
                "terms_count": len(terms),
                "abbreviations_count": len(abbreviations),
            },
        )


# Singleton
document_saver = DocumentSaver()
