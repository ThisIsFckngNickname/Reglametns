"""
Generator service — orchestrates the full document generation pipeline.

Pipeline:
1. Load holding profile → generators.data_loader
2. Load influencing documents → generators.data_loader
3. Load terms/abbreviations → generators.data_loader
4. Extract text from draft files → generators.text_extractor
5. [NEW] Search RAG for relevant approved document chunks
6. [NEW] Search web for topic information
7. Build prompt → prompt_builder
8. Call LLM → ollama_client
9. Parse response → generators.response_handler
10. Build .docx → docx_builder
11. Save as Document + DocumentVersion → DocumentSaver
12. Return document details
"""

import json
import logging
from typing import Optional

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_saver_service import document_saver
from app.services.docx_builder import docx_builder
from app.services.generators.data_loader import data_loader
from app.services.generators.text_extractor import text_extractor
from app.services.generators.response_handler import response_handler
from app.services.ollama_client import ollama_client
from app.services.prompt_builder import prompt_builder

logger = logging.getLogger(__name__)

# Rough token estimation: ~2 chars per token for Russian text
_CHARS_PER_TOKEN = 2
_PARAGRAPH_SEP = "\n\n"


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _truncate_by_paragraphs(text: str, max_chars: int) -> str:
    """Truncate text at paragraph boundary, keeping the HEAD."""
    if not text:
        return text
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_boundary = truncated.rfind(_PARAGRAPH_SEP)
    if last_boundary > max_chars // 2:
        truncated = text[:last_boundary]
    else:
        last_newline = truncated.rfind("\n")
        if last_newline > max_chars // 3:
            truncated = text[:last_newline]

    return truncated.rstrip() + "\n\n[Продолжение файла обрезано из-за ограничения длины...]"


def _distribute_token_budget(
    texts: list[tuple[str, str]],
    total_budget_tokens: int,
    system_padding_tokens: int = 3000,
) -> list[str]:
    """Distribute token budget across multiple file texts."""
    if not texts:
        return []

    budget_chars = (total_budget_tokens - system_padding_tokens) * _CHARS_PER_TOKEN
    if budget_chars <= 0:
        return [""] * len(texts)

    total_len = sum(len(t) for _, t in texts)
    if total_len <= budget_chars:
        return [t for _, t in texts]

    result = []
    for label, text in texts:
        if total_len == 0:
            result.append("")
            continue
        proportion = len(text) / total_len
        file_budget = max(int(budget_chars * proportion), 500)

        if len(text) <= file_budget:
            result.append(text)
        else:
            truncated = _truncate_by_paragraphs(text, file_budget)
            result.append(truncated)

    return result


class GeneratorService:
    """Orchestrates the full generation process."""

    def __init__(self, llm_client=None):
        self._llm_client = llm_client or ollama_client

    @property
    def llm(self):
        """Lazy LLM client resolution."""
        return self._llm_client

    async def generate(
        self,
        context_description: str,
        user: User,
        company_id: int,
        draft_files: Optional[list[FastAPIUploadFile]] = None,
        influencing_document_ids: Optional[list[int]] = None,
        db: Optional[AsyncSession] = None,
    ) -> DocumentResponse:
        """Full generation pipeline."""
        # 1. Load company profile
        company = await data_loader.load_company(company_id, db)

        # 2. Load influencing documents
        influencing_docs = await data_loader.load_influencing_documents(
            influencing_document_ids, company_id, db
        )

        # 3. Load terms/abbreviations from knowledge base
        terms = await data_loader.load_company_terms(company_id, db)

        # 4. Extract text from draft files
        drafts_content = await text_extractor.extract_draft_text(draft_files)

        # 5. Search RAG for relevant approved document chunks
        rag_chunks = []
        try:
            from app.services.rag_service import rag_service
            rag_chunks = await rag_service.search(
                query=context_description,
                company_id=company_id,
                top_k=settings.rag_max_chunks,
            )
            logger.info(f"RAG search returned {len(rag_chunks)} chunks")
        except Exception as e:
            logger.warning(f"RAG search failed (will continue without): {e}")

        # 6. Search web for topic information
        web_results = []
        if settings.web_search_enabled:
            try:
                from app.services.web_search_service import web_search_service
                web_results = await web_search_service.search(context_description)
                logger.info(f"Web search returned {len(web_results)} results")
            except Exception as e:
                logger.warning(f"Web search failed (will continue without): {e}")

        # 7. Log diagnostics
        logger.info(
            "Generation diagnostics: "
            f"context_len={len(context_description)}, "
            f"draft_files={len(draft_files) if draft_files else 0}, "
            f"drafts_chars={len(drafts_content)}, "
            f"rag_chunks={len(rag_chunks)}, "
            f"web_results={len(web_results)}, "
            f"influencing_docs={len(influencing_docs)}, "
            f"terms={len(terms)}"
        )

        # 8. Truncate large content proportionally
        max_prompt = settings.generation_max_prompt_tokens

        for doc in influencing_docs:
            if "full_text" in doc:
                doc["full_text"] = _truncate_by_paragraphs(
                    doc["full_text"],
                    max_chars=max_prompt * _CHARS_PER_TOKEN // 4,
                )

        if draft_files and drafts_content:
            file_sections = []
            current_file = []
            current_label = "unknown"
            for line in drafts_content.split("\n"):
                if line.startswith("--- Файл:") and line.endswith(" ---"):
                    if current_file:
                        file_sections.append((current_label, "\n".join(current_file)))
                    current_label = line
                    current_file = []
                else:
                    current_file.append(line)
            if current_file:
                file_sections.append((current_label, "\n".join(current_file)))

            if file_sections:
                truncated_sections = _distribute_token_budget(
                    file_sections, max_prompt, system_padding_tokens=5000
                )
                drafts_content = "\n".join(
                    f"{label}\n{content}"
                    for label, content in zip(
                        [s[0] for s in file_sections], truncated_sections
                    )
                )

        # 9. Build prompt with RAG and web context
        style_patterns_text = response_handler.format_style_patterns_for_prompt(
            company.style_settings
        )
        messages = prompt_builder.build_messages(
            company=company,
            context_description=context_description,
            drafts_content=drafts_content,
            terms=terms,
            influencing_docs=influencing_docs,
            style_patterns=style_patterns_text,
            rag_chunks=rag_chunks,
            web_results=web_results,
        )

        # 10. Call LLM
        raw_response = await self.llm.chat_completion(messages)
        logger.info(f"LLM response received: {len(raw_response)} chars")

        # 11. Parse JSON response
        result = await response_handler.parse_response(raw_response)
        result["generated_with_mock"] = False

        # 12. Build .docx
        doc_title = result.get("title", "Сгенерированный документ")
        output_path = response_handler.get_output_path(company_id, doc_title)
        docx_builder.build(result, company, output_path)

        # 13. Save as Document + DocumentVersion
        return await document_saver.save_generated_document(
            company_id=company_id,
            doc_title=doc_title,
            description=result.get("description", ""),
            output_path=output_path,
            sections_count=len(result.get("sections", [])),
            terms=result.get("terms", []),
            abbreviations=result.get("abbreviations", []),
            user=user,
            db=db,
        )

    async def generate_mock(
        self,
        user: User,
        company_id: int,
        db: AsyncSession,
    ) -> DocumentResponse:
        """Generate a document using mock data (no LLM)."""
        mock_result = response_handler.get_mock_response()
        mock_result["generated_with_mock"] = True

        company = await data_loader.load_company(company_id, db)

        doc_title = mock_result.get("title", "Сгенерированный документ (демо-режим)")
        output_path = response_handler.get_output_path(company_id, doc_title)
        docx_builder.build(mock_result, company, output_path)

        return await document_saver.save_generated_document(
            company_id=company_id,
            doc_title=doc_title,
            description=mock_result.get("description", ""),
            output_path=output_path,
            sections_count=len(mock_result.get("sections", [])),
            terms=mock_result.get("terms", []),
            abbreviations=mock_result.get("abbreviations", []),
            user=user,
            db=db,
        )

    # ── Backward-compatible private method delegates ─────────────────

    async def _parse_response(self, raw_response: str) -> dict:
        return await response_handler.parse_response(raw_response)

    def _format_style_patterns_for_prompt(self, style_settings: Optional[dict]) -> str:
        return response_handler.format_style_patterns_for_prompt(style_settings)

    async def _extract_draft_text(
        self,
        files: Optional[list[FastAPIUploadFile]],
    ) -> str:
        return await text_extractor.extract_draft_text(files)


    # ── V2 (B1): New full-context generation method ──────────────────

    async def generate_document(
        self,
        topic: str,
        company_id: int,
        document_type: str = "regulation",
        user_id: int | None = None,
        draft_file_path: str | None = None,
        influence_document_ids: list[int] | None = None,
        search_enabled: bool = True,
        db: AsyncSession | None = None,
    ) -> DocumentResponse:
        """Generate a document using all available knowledge sources (V2).

        Pipeline:
        1. Collect context (6 sources)
        2. Build prompt (PromptBuilder V2)
        3. Call LLM
        4. Parse response
        5. Build .docx
        6. Save document

        Args:
            topic: Document topic (e.g. "Регламент по ГСМ").
            company_id: Company (holding) ID.
            document_type: Document type key from DOCUMENT_TYPES.
            user_id: Creator user ID (optional, for audit).
            draft_file_path: Path to draft file in storage (optional).
            influence_document_ids: IDs of influencing documents (optional).
            search_enabled: Enable web search (default True).
            db: Database session.

        Returns:
            DocumentResponse with generated document metadata.
        """
        # 1. Load company
        company = await data_loader.load_company(company_id, db)

        # 2. Load company-wide terms (CompanyTerm)
        company_terms = await data_loader.load_company_terms_list(company_id, db)

        # 3. Load company-wide abbreviations (CompanyAbbreviation)
        company_abbreviations = await data_loader.load_company_abbreviations_list(company_id, db)

        # 4. Search ChromaDB for similar documents
        similar_chunks = []
        try:
            from app.services.rag_service import rag_service
            similar_chunks = await rag_service.search(
                query=topic,
                company_id=company_id,
                top_k=5,
            )
            logger.info(f"RAG search returned {len(similar_chunks)} chunks for V2")
        except Exception as e:
            logger.warning(f"RAG search failed (V2 will continue without): {e}")

        # 5. Web search
        web_results_text = None
        if search_enabled:
            try:
                from app.services.web_search_service import web_search_service
                web_results_text = await web_search_service.enrich_prompt(topic)
                if web_results_text:
                    logger.info(f"Web search enrich returned {len(web_results_text)} chars")
                else:
                    logger.info("Web search enrich returned no results")
            except Exception as e:
                logger.warning(f"Web search failed (V2 will continue without): {e}")

        # 6. Extract draft text
        draft_text = await data_loader.load_draft_text(draft_file_path)

        # 7. Load influencing documents
        influencing_docs = await data_loader.load_influencing_documents(
            influence_document_ids, company_id, db
        )

        # 8. Log diagnostics
        logger.info(
            "V2 Generation diagnostics: "
            f"topic_len={len(topic)}, "
            f"terms={len(company_terms)}, "
            f"abbreviations={len(company_abbreviations)}, "
            f"rag_chunks={len(similar_chunks)}, "
            f"web_results={'yes' if web_results_text else 'no'}, "
            f"draft_chars={len(draft_text)}, "
            f"influencing_docs={len(influencing_docs)}"
        )

        # 9. Build V2 prompt
        messages = prompt_builder.build_messages_v2(
            company=company,
            topic=topic,
            document_type=document_type,
            company_terms=company_terms,
            company_abbreviations=company_abbreviations,
            similar_chunks=similar_chunks,
            web_results_text=web_results_text,
            draft_text=draft_text,
            influencing_docs=influencing_docs,
        )

        # 10. Call LLM
        raw_response = await self.llm.chat_completion(messages)
        logger.info(f"LLM V2 response received: {len(raw_response)} chars")

        # 11. Parse JSON response
        result = await response_handler.parse_response(raw_response)
        result["generated_with_mock"] = False

        # 12. Build .docx
        doc_title = result.get("title", topic)
        output_path = response_handler.get_output_path(company_id, doc_title)
        docx_builder.build(result, company, output_path)

        # 13. Load user for save
        user = None
        if user_id is not None:
            from app.models.user import User as UserModel
            from sqlalchemy import select
            user_stmt = select(UserModel).where(UserModel.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

        # 14. Save as Document + DocumentVersion
        return await document_saver.save_generated_document(
            company_id=company_id,
            doc_title=doc_title,
            description=result.get("description", ""),
            output_path=output_path,
            sections_count=len(result.get("sections", [])),
            terms=result.get("terms", []),
            abbreviations=result.get("abbreviations", []),
            user=user,
            db=db,
            document_type=document_type,
        )


# Singleton
generator_service = GeneratorService()
