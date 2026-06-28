"""
Document Persistence Service.
Handles saving parsed document data (sections, tables, terms, abbreviations) to the database.
Used by both document upload and version creation.
"""

import json
import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_section import DocumentSection
from app.models.document_table import DocumentTable
from app.models.document_term import DocumentTerm
from app.models.document_version import DocumentVersion

logger = logging.getLogger(__name__)


class DocumentPersistenceService:
    """Handles persistence of parsed document data."""

    async def persist_parse_result(
        self,
        parse_result: Any,
        version: DocumentVersion,
        document_id: int,
        db: AsyncSession,
    ) -> None:
        """Save sections, tables, terms, abbreviations, and full_text to DB.

        Args:
            parse_result: ParseResult with .sections, .tables, .terms, .abbreviations, .lists.
            version: DocumentVersion to associate section/table data with.
            document_id: Document ID for terms/abbreviations.
            db: Database session.
        """
        section_id_map = await self._save_sections(parse_result.sections, version, db)
        await self._save_tables(parse_result.tables, version, section_id_map, db)
        await self._save_terms(parse_result.terms, document_id, db)
        await self._save_abbreviations(parse_result.abbreviations, document_id, db)
        self._build_and_set_full_text(parse_result.sections, version)
        await self._save_lists(parse_result.lists, version)

        await db.flush()

    async def _save_sections(
        self,
        sections_data: list[dict],
        version: DocumentVersion,
        db: AsyncSession,
    ) -> dict[int, int]:
        """Save sections with parent_id hierarchy.

        Returns:
            dict mapping order_num -> database id for table section lookups.
        """
        section_id_map: dict[int, int] = {}
        for section_data in sections_data:
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
        for section_data in sections_data:
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

        return section_id_map

    async def _save_tables(
        self,
        tables_data: list[dict],
        version: DocumentVersion,
        section_id_map: dict[int, int],
        db: AsyncSession,
    ) -> None:
        """Save tables with section_id mapping from order_num to DB id."""
        for table_data in tables_data:
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

    async def _save_terms(
        self,
        terms_data: list[dict],
        document_id: int,
        db: AsyncSession,
    ) -> None:
        """Save terms deduplicated by normalized term text."""
        seen_terms: set[str] = set()
        for term_data in terms_data:
            term_key = term_data["term"].lower().strip()
            if term_key not in seen_terms:
                seen_terms.add(term_key)
                term = DocumentTerm(
                    document_id=document_id,
                    term=term_data["term"],
                    definition=term_data["definition"],
                )
                db.add(term)

    async def _save_abbreviations(
        self,
        abbrs_data: list[dict],
        document_id: int,
        db: AsyncSession,
    ) -> None:
        """Save abbreviations deduplicated by normalized abbreviation text."""
        seen_abbrs: set[str] = set()
        for abbr_data in abbrs_data:
            abbr_key = abbr_data["abbreviation"].lower().strip()
            if abbr_key not in seen_abbrs:
                seen_abbrs.add(abbr_key)
                abbr = DocumentAbbreviation(
                    document_id=document_id,
                    abbreviation=abbr_data["abbreviation"],
                    full_form=abbr_data["full_form"],
                )
                db.add(abbr)

    def _build_and_set_full_text(
        self,
        sections_data: list[dict],
        version: DocumentVersion,
    ) -> None:
        """Build full_text from sections and set it on the version in-place."""
        parts = []
        for section in sections_data:
            title = section.get("title", "")
            content = section.get("content", "")
            if title:
                parts.append(title)
            if content:
                parts.append(content.strip())
        version.full_text = "\n\n".join(parts)

    async def _save_lists(
        self,
        lists_data: list[dict],
        version: DocumentVersion,
    ) -> None:
        """Save lists data as JSON in version_notes if version_notes is empty."""
        if lists_data and not version.version_notes:
            version.version_notes = json.dumps(
                {"lists": lists_data},
                ensure_ascii=False,
            )


# Singleton
document_persistence_service = DocumentPersistenceService()
