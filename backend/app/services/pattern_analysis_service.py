"""
Pattern Analysis Service.

When a document is approved, this service:
1. Extracts the document structure (sections hierarchy, depth)
2. Analyzes writing style (typical phrases, sentence length, formatting)
3. Extracts all terms and abbreviations as holding-level knowledge
4. Updates the holding profile with the extracted patterns
5. Marks the document as analyzed
"""

import json
import logging
from collections import Counter
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.document_section import DocumentSection
from app.models.document_term import DocumentTerm
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.holding import Holding

logger = logging.getLogger(__name__)


class PatternAnalysisService:
    """Analyzes approved documents and extracts patterns for the holding."""

    async def analyze_document(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Analyze an approved document and update holding patterns.

        Args:
            document_id: ID of the document to analyze.
            db: Database session.

        Returns:
            Dict with analysis results.
        """
        # Load document with all related data
        doc = await self._load_document(document_id, db)
        if doc is None:
            return {"error": "Document not found"}

        if doc.was_analyzed:
            return {"error": "Document already analyzed", "already_analyzed": True}

        # Get the latest version
        latest_version = await self._get_latest_version(doc.id, db)
        if latest_version is None:
            return {"error": "No versions found"}

        # 1. Extract structure patterns
        structure = await self._extract_structure(latest_version, db)

        # 2. Extract style patterns from sections content
        style = await self._extract_style(latest_version, db)

        # 3. Collect holding-level terms and abbreviations
        terms_data = await self._collect_terms(doc.id, db)
        abbrs_data = await self._collect_abbreviations(doc.id, db)

        # 4. Update holding profile
        holding = await self._load_holding(doc.holding_id, db)
        if holding:
            await self._update_holding_patterns(
                holding, structure, style, terms_data, abbrs_data, db
            )

        # 5. Mark document as analyzed
        doc.was_analyzed = True
        await db.flush()

        return {
            "document_id": doc.id,
            "holding_id": doc.holding_id,
            "structure_extracted": bool(structure.get("sections")),
            "style_extracted": bool(style.get("typical_phrases") or style.get("avg_sentence_length", 0) > 0),
            "terms_collected": len(terms_data),
            "abbreviations_collected": len(abbrs_data),
        }

    async def _load_document(self, document_id: int, db: AsyncSession) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_latest_version(self, document_id: int, db: AsyncSession) -> Optional[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _extract_structure(self, version: DocumentVersion, db: AsyncSession) -> dict:
        """Extract document structure: section hierarchy, depth, patterns."""
        stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_version_id == version.id)
            .order_by(DocumentSection.order_num)
        )
        result = await db.execute(stmt)
        sections = result.scalars().all()

        if not sections:
            return {"sections": [], "max_depth": 0, "total_sections": 0}

        # Calculate hierarchy depth
        max_depth = max((s.level for s in sections), default=0)

        # Group by level to find typical structure
        level_counts = {}
        for s in sections:
            level_counts[s.level] = level_counts.get(s.level, 0) + 1

        # Extract section title patterns (typical headings)
        section_titles = [s.title for s in sections if s.level == 1]

        return {
            "sections": [
                {"title": s.title, "level": s.level, "order_num": s.order_num}
                for s in sections
            ],
            "max_depth": max_depth,
            "total_sections": len(sections),
            "level_distribution": level_counts,
            "top_level_titles": section_titles,
        }

    async def _extract_style(self, version: DocumentVersion, db: AsyncSession) -> dict:
        """Extract writing style patterns from section content."""
        stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_version_id == version.id)
            .order_by(DocumentSection.order_num)
        )
        result = await db.execute(stmt)
        sections = result.scalars().all()

        if not sections:
            return {"typical_phrases": [], "avg_sentence_length": 0}

        # Collect all text
        all_text = " ".join(s.content or "" for s in sections)

        # Extract typical opening phrases (first 50 chars of each section)
        typical_phrases = []
        for s in sections:
            content = (s.content or "").strip()
            if content:
                # Get first sentence
                first_sentence = content.split(".")[0].strip()
                if len(first_sentence) > 20:
                    typical_phrases.append(first_sentence[:100])

        # Count unique phrases that appear in multiple sections
        phrase_counter = Counter(typical_phrases)
        common_phrases = [p for p, c in phrase_counter.most_common(10) if c > 1]

        # Calculate average sentence length
        sentences = [s.strip() for s in all_text.replace("\n", " ").split(".") if s.strip()]
        avg_sentence_length = 0
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)

        return {
            "typical_phrases": common_phrases[:10],
            "avg_sentence_length": round(avg_sentence_length, 1),
            "total_sentences": len(sentences),
            "total_words": len(all_text.split()),
        }

    async def _collect_terms(self, document_id: int, db: AsyncSession) -> list[dict]:
        """Collect terms from a document (for holding-level knowledge base)."""
        stmt = select(DocumentTerm).where(DocumentTerm.document_id == document_id)
        result = await db.execute(stmt)
        terms = result.scalars().all()
        return [{"term": t.term, "definition": t.definition} for t in terms]

    async def _collect_abbreviations(self, document_id: int, db: AsyncSession) -> list[dict]:
        """Collect abbreviations from a document."""
        stmt = select(DocumentAbbreviation).where(DocumentAbbreviation.document_id == document_id)
        result = await db.execute(stmt)
        abbrs = result.scalars().all()
        return [{"abbreviation": a.abbreviation, "full_form": a.full_form} for a in abbrs]

    async def _load_holding(self, holding_id: int, db: AsyncSession) -> Optional[Holding]:
        stmt = select(Holding).where(Holding.id == holding_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_holding_patterns(
        self,
        holding: Holding,
        structure: dict,
        style: dict,
        terms: list[dict],
        abbreviations: list[dict],
        db: AsyncSession,
    ) -> None:
        """Update holding profile with extracted patterns."""
        # Update document_structure
        current_structure = {}
        if holding.document_structure:
            if isinstance(holding.document_structure, str):
                try:
                    current_structure = json.loads(holding.document_structure)
                except (json.JSONDecodeError, TypeError):
                    current_structure = {}
            else:
                current_structure = dict(holding.document_structure)

        current_structure["max_depth"] = max(
            current_structure.get("max_depth", 0),
            structure.get("max_depth", 0),
        )
        current_structure["total_sections"] = structure.get("total_sections", 0)
        current_structure["level_distribution"] = structure.get("level_distribution", {})

        # Merge top-level titles (avoiding duplicates)
        existing_titles = set(current_structure.get("top_level_titles", []))
        for title in structure.get("top_level_titles", []):
            existing_titles.add(title)
        current_structure["top_level_titles"] = list(existing_titles)

        holding.document_structure = current_structure

        # Update style_settings
        current_style = {}
        if holding.style_settings:
            if isinstance(holding.style_settings, str):
                try:
                    current_style = json.loads(holding.style_settings)
                except (json.JSONDecodeError, TypeError):
                    current_style = {}
            else:
                current_style = dict(holding.style_settings)

        # Merge style patterns
        existing_phrases = set(current_style.get("typical_phrases", []))
        for phrase in style.get("typical_phrases", []):
            existing_phrases.add(phrase)
        current_style["typical_phrases"] = list(existing_phrases)

        # Merge avg_sentence_length (weighted average)
        old_avg = current_style.get("avg_sentence_length", 0)
        new_avg = style.get("avg_sentence_length", 0)
        old_count = current_style.get("documents_analyzed", 0)
        new_count = old_count + 1
        if old_count > 0 and new_avg > 0:
            combined_avg = (old_avg * old_count + new_avg) / new_count
        else:
            combined_avg = new_avg or old_avg

        current_style["avg_sentence_length"] = round(combined_avg, 1)
        current_style["documents_analyzed"] = new_count

        holding.style_settings = current_style

        # Log the update
        logger.info(
            f"Updated holding {holding.id} patterns: "
            f"structure_depth={structure.get('max_depth')}, "
            f"phrases_added={len(style.get('typical_phrases', []))}, "
            f"total_analyzed={new_count}"
        )


# Singleton
pattern_analysis_service = PatternAnalysisService()
