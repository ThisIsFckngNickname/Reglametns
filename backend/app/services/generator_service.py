"""
Generator service — orchestrates the full document generation pipeline.

Pipeline:
1. Load holding profile
2. Load influencing documents from DB
3. Load terms/abbreviations from knowledge base
4. Extract text from draft files
5. Build prompt (system + user)
6. Call GigaChat
7. Parse JSON response (with retries for malformed JSON)
8. Build .docx
9. Save as Document + DocumentVersion
10. Return document details
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException
from app.models.document import Document
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_term import DocumentTerm
from app.models.document_version import DocumentVersion
from app.models.holding import Holding
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.docx_builder import docx_builder
from app.services.gigachat_service import GigaChatClient, MOCK_RESPONSE, gigachat_client
from app.services.prompt_builder import prompt_builder
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


class GeneratorService:
    """Orchestrates the full generation process."""

    def __init__(self, giga_client: Optional[GigaChatClient] = None):
        self.gigachat = giga_client or gigachat_client

    async def generate(
        self,
        context_description: str,
        user: User,
        holding_id: int,
        draft_files: Optional[list[FastAPIUploadFile]] = None,
        influencing_document_ids: Optional[list[int]] = None,
        db: Optional[AsyncSession] = None,
    ) -> DocumentResponse:
        """Full generation pipeline.

        Args:
            context_description: User description of what the document should regulate.
            user: The requesting user.
            holding_id: Active holding ID.
            draft_files: Optional list of uploaded draft files.
            influencing_document_ids: Optional list of document IDs that influence this document.
            db: Database session (required for persistence).

        Returns:
            DocumentResponse with the generated document details.
        """
        # 1. Load holding profile
        holding = await self._load_holding(holding_id, db)

        # 2. Load influencing documents
        influencing_docs = await self._load_influencing_documents(
            influencing_document_ids, holding_id, db
        )

        # 3. Load terms/abbreviations from knowledge base
        terms = await self._load_holding_terms(holding_id, db)

        # 4. Extract text from draft files
        drafts_content = await self._extract_draft_text(draft_files)

        # 5. Build prompt
        messages = prompt_builder.build_messages(
            holding=holding,
            context_description=context_description,
            drafts_content=drafts_content,
            terms=terms,
            influencing_docs=influencing_docs,
        )

        # 6. Call GigaChat
        is_mock = self.gigachat.is_mock
        try:
            raw_response = await self.gigachat.chat_completion(messages)
        except Exception as e:
            logger.error(f"GigaChat generation failed: {e}", exc_info=True)
            # Fallback to mock response on error
            raw_response = json.dumps(MOCK_RESPONSE, ensure_ascii=False)
            is_mock = True

        # 7. Parse JSON response
        result = await self._parse_response(raw_response)

        # Add mock flag
        result["generated_with_mock"] = is_mock

        # 8. Build .docx
        doc_title = result.get("title", "Сгенерированный документ")
        output_path = self._get_output_path(holding_id, doc_title)
        docx_builder.build(result, holding, output_path)

        # 9. Save as Document + DocumentVersion
        document = Document(
            holding_id=holding_id,
            title=doc_title,
            description=result.get("description", ""),
            status="draft",
            created_by=user.id,
        )
        db.add(document)
        await db.flush()

        # Read file content for storage
        with open(output_path, "rb") as f:
            file_content = f.read()

        # Save to storage
        fake_file = FastAPIUploadFile(
            filename=os.path.basename(output_path),
            file=BytesIO(file_content),
        )
        rel_path = await storage.save(fake_file, holding_id, document.id, 1)

        # Create DocumentVersion
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

        # Save terms
        for term_item in result.get("terms", []):
            term = DocumentTerm(
                document_id=document.id,
                term=term_item.get("term", ""),
                definition=term_item.get("definition", ""),
            )
            db.add(term)

        # Save abbreviations
        for abbr_item in result.get("abbreviations", []):
            abbr = DocumentAbbreviation(
                document_id=document.id,
                abbreviation=abbr_item.get("abbreviation", ""),
                full_form=abbr_item.get("full_form", ""),
            )
            db.add(abbr)

        await db.flush()

        return DocumentResponse(
            id=document.id,
            holding_id=holding_id,
            title=doc_title,
            description=result.get("description", ""),
            status="draft",
            created_by=user.id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            versions_count=1,
            sections_count=len(result.get("sections", [])),
            tables_count=0,
            terms_count=len(result.get("terms", [])),
            abbreviations_count=len(result.get("abbreviations", [])),
        )

    async def _load_holding(self, holding_id: int, db: AsyncSession) -> Holding:
        """Load holding profile by ID."""
        stmt = select(Holding).where(Holding.id == holding_id)
        result = await db.execute(stmt)
        holding = result.scalar_one_or_none()
        if holding is None:
            raise BadRequestException(
                code="HOLDING_NOT_FOUND",
                message="Холдинг не найден",
                field="holding_id",
            )
        return holding

    async def _load_influencing_documents(
        self,
        document_ids: Optional[list[int]],
        holding_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Load influencing documents from DB by IDs."""
        if not document_ids:
            return []

        from app.models.document import Document as DocModel

        docs = []
        for doc_id in document_ids:
            stmt = select(DocModel).where(
                DocModel.id == doc_id,
                DocModel.holding_id == holding_id,
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                docs.append({
                    "title": doc.title,
                    "source": f"Внутренний документ х. {holding_id}",
                })
        return docs

    async def _load_holding_terms(
        self,
        holding_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Load terms and definitions from all documents in the holding."""
        from app.models.document import Document as DocModel

        # Get all document IDs for this holding
        doc_stmt = select(DocModel.id).where(DocModel.holding_id == holding_id)
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

    async def _extract_draft_text(
        self,
        files: Optional[list[FastAPIUploadFile]],
    ) -> str:
        """Extract text from uploaded draft files (docx/pdf)."""
        if not files:
            return ""

        texts = []
        for file in files:
            content = await file.read()
            filename = file.filename or "draft"
            ext = os.path.splitext(filename)[1].lower()

            if ext == ".docx":
                text = self._extract_docx_text(content)
            elif ext == ".pdf":
                text = self._extract_pdf_text(content)
            else:
                text = content.decode("utf-8", errors="ignore")

            if text:
                header = f"\n--- Содержимое файла: {filename} ---\n"
                texts.append(header + text)

        return "\n".join(texts)

    def _extract_docx_text(self, content: bytes) -> str:
        """Extract text from .docx content bytes."""
        try:
            from docx import Document as DocxDocument

            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                doc = DocxDocument(tmp_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n".join(paragraphs)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to extract docx text: {e}")
            return ""

    def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text from PDF content bytes."""
        try:
            import fitz  # PyMuPDF

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                doc = fitz.open(tmp_path)
                texts = []
                for page in doc:
                    texts.append(page.get_text())
                doc.close()
                return "\n".join(texts)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to extract PDF text: {e}")
            return ""

    async def _parse_response(self, raw_response: str) -> dict:
        """Parse GigaChat JSON response, with fallback for malformed JSON.

        Strategy:
        1. Try json.loads() directly
        2. If fails, try to extract JSON from markdown code block (```json ... ```)
        3. If still fails, raise BadRequestException
        """
        if not raw_response or not raw_response.strip():
            logger.warning("Empty response from GigaChat, using mock")
            return dict(MOCK_RESPONSE)

        # Strategy 1: Direct parse
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        json_match = re.search(
            r"```(?:json)?\s*([\s\S]*?)```", raw_response, re.IGNORECASE
        )
        if json_match:
            extracted = json_match.group(1).strip()
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Try to find JSON-like structure in the text
        json_match = re.search(r"(\{[\s\S]*\})", raw_response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse GigaChat response as JSON: {raw_response[:500]}")
        raise BadRequestException(
            code="GENERATION_FAILED",
            message="Не удалось обработать ответ от GigaChat. Попробуйте снова.",
        )

    def _get_output_path(self, holding_id: int, title: str) -> str:
        """Generate output path for the generated .docx file.

        Returns a path in the system temp directory.
        """
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()[:50]
        safe_title = safe_title.replace(" ", "_")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        filename = f"generated_{holding_id}_{safe_title}_{timestamp}.docx"
        output_dir = os.path.join(tempfile.gettempdir(), "srp_generated")
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)

    async def generate_mock(
        self,
        user: User,
        holding_id: int,
        db: AsyncSession,
    ) -> DocumentResponse:
        """Generate a document using mock data (no GigaChat)."""
        mock_result = dict(MOCK_RESPONSE)
        mock_result["generated_with_mock"] = True

        holding = await self._load_holding(holding_id, db)

        doc_title = mock_result.get("title", "Сгенерированный документ (демо-режим)")
        output_path = self._get_output_path(holding_id, doc_title)
        docx_builder.build(mock_result, holding, output_path)

        document = Document(
            holding_id=holding_id,
            title=doc_title,
            description=mock_result.get("description", ""),
            status="draft",
            created_by=user.id,
        )
        db.add(document)
        await db.flush()

        with open(output_path, "rb") as f:
            file_content = f.read()

        fake_file = FastAPIUploadFile(
            filename=os.path.basename(output_path),
            file=BytesIO(file_content),
        )
        rel_path = await storage.save(fake_file, holding_id, document.id, 1)

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
        await db.flush()

        return DocumentResponse(
            id=document.id,
            holding_id=holding_id,
            title=doc_title,
            description=mock_result.get("description", ""),
            status="draft",
            created_by=user.id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            versions_count=1,
            sections_count=len(mock_result.get("sections", [])),
            tables_count=0,
            terms_count=len(mock_result.get("terms", [])),
            abbreviations_count=len(mock_result.get("abbreviations", [])),
        )


# Singleton
generator_service = GeneratorService()
