"""
Tests for Pattern Analysis Service.

Covers:
1. analyze_document basic flow
2. Document already analyzed
3. Document not found
4. Structure extraction
5. Style extraction
6. Status change trigger via DocumentService
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.document_section import DocumentSection
from app.models.document_term import DocumentTerm
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_status_log import DocumentStatusLog
from app.models.company import Company
from app.models.user import User
from app.services.pattern_analysis_service import PatternAnalysisService
from app.services.document_service import DocumentService
from app.schemas.document import DocumentUpdate


# ─── Helpers ──────────────────────────────────────────────────────────────

async def _create_test_document(
    session: AsyncSession,
    company_id: int,
    created_by: int,
    status: DocumentStatus = DocumentStatus.DRAFT,
    was_analyzed: bool = False,
) -> Document:
    """Create a minimal document for testing."""
    doc = Document(
        company_id=company_id,
        title="Test Document",
        description="A test document for pattern analysis",
        status=status,
        created_by=created_by,
        was_analyzed=was_analyzed,
    )
    session.add(doc)
    await session.flush()
    return doc


async def _create_test_version(
    session: AsyncSession,
    document_id: int,
    version_number: int = 1,
) -> DocumentVersion:
    """Create a minimal version for testing."""
    ver = DocumentVersion(
        document_id=document_id,
        version_number=version_number,
        file_path="test/path.docx",
        file_type="docx",
        file_size=1000,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        uploaded_by=None,
    )
    session.add(ver)
    await session.flush()
    return ver


async def _create_test_section(
    session: AsyncSession,
    version_id: int,
    title: str,
    level: int,
    order_num: int,
    content: str = "",
) -> DocumentSection:
    """Create a section for testing."""
    sec = DocumentSection(
        document_version_id=version_id,
        title=title,
        level=level,
        order_num=order_num,
        content=content,
    )
    session.add(sec)
    await session.flush()
    return sec


async def _create_test_term(
    session: AsyncSession,
    document_id: int,
    term: str,
    definition: str,
) -> DocumentTerm:
    """Create a term for testing."""
    t = DocumentTerm(
        document_id=document_id,
        term=term,
        definition=definition,
    )
    session.add(t)
    await session.flush()
    return t


async def _create_test_abbreviation(
    session: AsyncSession,
    document_id: int,
    abbreviation: str,
    full_form: str,
) -> DocumentAbbreviation:
    """Create an abbreviation for testing."""
    a = DocumentAbbreviation(
        document_id=document_id,
        abbreviation=abbreviation,
        full_form=full_form,
    )
    session.add(a)
    await session.flush()
    return a


# ─── Tests ────────────────────────────────────────────────────────────────

class TestPatternAnalysisService:
    """Tests for PatternAnalysisService."""

    @pytest.mark.asyncio
    async def test_analyze_document_basic_flow(
        self, test_session: AsyncSession
    ):
        """Should analyze a document and update company patterns."""
        # Arrange
        company = Company(name="Analysis Company", inn="7701000001", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1)
        ver = await _create_test_version(test_session, doc.id)
        await _create_test_section(
            test_session, ver.id, "Общие положения", 1, 1,
            "Настоящий документ определяет основные правила работы."
        )
        await _create_test_section(
            test_session, ver.id, "Термины и определения", 1, 2,
            "В настоящем документе используются следующие термины."
        )
        await _create_test_term(test_session, doc.id, "Регламент", "Документ, устанавливающий правила")
        await _create_test_abbreviation(test_session, doc.id, "ООО", "Общество с ограниченной ответственностью")

        service = PatternAnalysisService()

        # Act
        result = await service.analyze_document(document_id=doc.id, db=test_session)

        # Assert
        assert result["document_id"] == doc.id
        assert result["company_id"] == company.id
        assert result["structure_extracted"] is True
        assert result["style_extracted"] is True
        assert result["terms_collected"] == 1
        assert result["abbreviations_collected"] == 1

        # Verify document was marked as analyzed
        await test_session.refresh(doc)
        assert doc.was_analyzed is True

        # Verify company patterns were updated
        await test_session.refresh(company)
        assert company.document_structure is not None
        assert company.style_settings is not None
        assert "max_depth" in company.document_structure
        assert "typical_phrases" in company.style_settings

    @pytest.mark.asyncio
    async def test_analyze_document_already_analyzed(
        self, test_session: AsyncSession
    ):
        """Should return error if document was already analyzed."""
        # Arrange
        company = Company(name="Analyzed Company", inn="7701000002", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(
            test_session, company.id, 1, was_analyzed=True
        )

        service = PatternAnalysisService()

        # Act
        result = await service.analyze_document(document_id=doc.id, db=test_session)

        # Assert
        assert "already_analyzed" in result
        assert result["already_analyzed"] is True

    @pytest.mark.asyncio
    async def test_analyze_document_not_found(
        self, test_session: AsyncSession
    ):
        """Should return error for non-existent document."""
        service = PatternAnalysisService()

        # Act
        result = await service.analyze_document(document_id=99999, db=test_session)

        # Assert
        assert result["error"] == "Document not found"

    @pytest.mark.asyncio
    async def test_analyze_document_no_versions(
        self, test_session: AsyncSession
    ):
        """Should return error if document has no versions."""
        # Arrange
        company = Company(name="NoVersion Company", inn="7701000003", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1)

        service = PatternAnalysisService()

        # Act
        result = await service.analyze_document(document_id=doc.id, db=test_session)

        # Assert
        assert result["error"] == "No versions found"

    @pytest.mark.asyncio
    async def test_extract_structure(
        self, test_session: AsyncSession
    ):
        """Should extract section hierarchy correctly."""
        # Arrange
        company = Company(name="Structure Company", inn="7701000004", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1)
        ver = await _create_test_version(test_session, doc.id)
        await _create_test_section(test_session, ver.id, "Глава 1", 1, 1, "Content 1")
        await _create_test_section(test_session, ver.id, "Глава 2", 1, 2, "Content 2")
        await _create_test_section(test_session, ver.id, "Раздел 2.1", 2, 3, "Content 2.1")
        await _create_test_section(test_session, ver.id, "Раздел 2.2", 2, 4, "Content 2.2")
        await _create_test_section(test_session, ver.id, "Подраздел 2.2.1", 3, 5, "Content 2.2.1")

        service = PatternAnalysisService()

        # Act
        structure = await service._extract_structure(ver, test_session)

        # Assert
        assert structure["total_sections"] == 5
        assert structure["max_depth"] == 3
        assert structure["level_distribution"] == {1: 2, 2: 2, 3: 1}
        assert len(structure["top_level_titles"]) == 2
        assert "Глава 1" in structure["top_level_titles"]

    @pytest.mark.asyncio
    async def test_extract_style(
        self, test_session: AsyncSession
    ):
        """Should extract style patterns from section content."""
        # Arrange
        company = Company(name="Style Company", inn="7701000005", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1)
        ver = await _create_test_version(test_session, doc.id)
        await _create_test_section(
            test_session, ver.id, "Раздел 1", 1, 1,
            "Настоящий документ устанавливает порядок выполнения работ. "
            "Он распространяется на всех сотрудников."
        )
        await _create_test_section(
            test_session, ver.id, "Раздел 2", 1, 2,
            "Настоящий документ определяет требования к документации. "
            "Все положения обязательны к исполнению."
        )

        service = PatternAnalysisService()

        # Act
        style = await service._extract_style(ver, test_session)

        # Assert
        assert style["total_sentences"] == 4
        assert style["total_words"] > 0
        assert style["avg_sentence_length"] > 0

    @pytest.mark.asyncio
    async def test_collect_terms_and_abbreviations(
        self, test_session: AsyncSession
    ):
        """Should collect terms and abbreviations from a document."""
        # Arrange
        company = Company(name="Collect Company", inn="7701000006", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1)
        await _create_test_term(test_session, doc.id, "Регламент", "Правила работы")
        await _create_test_term(test_session, doc.id, "Инструкция", "Руководство к действию")
        await _create_test_abbreviation(test_session, doc.id, "ООО", "Общество с ограниченной ответственностью")
        await _create_test_abbreviation(test_session, doc.id, "АО", "Акционерное общество")

        service = PatternAnalysisService()

        # Act
        terms = await service._collect_terms(doc.id, test_session)
        abbrs = await service._collect_abbreviations(doc.id, test_session)

        # Assert
        assert len(terms) == 2
        assert len(abbrs) == 2
        assert any(t["term"] == "Регламент" for t in terms)
        assert any(a["abbreviation"] == "ООО" for a in abbrs)


class TestStatusChangeTrigger:
    """Tests for status change logging and pattern analysis trigger."""

    @pytest.mark.asyncio
    async def test_status_change_creates_log(
        self, test_session: AsyncSession
    ):
        """Should create a DocumentStatusLog when status changes."""
        # Arrange
        company = Company(name="StatusLog Company", inn="7701000007", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1, status=DocumentStatus.DRAFT)

        service = DocumentService()

        # Act
        update = DocumentUpdate(status=DocumentStatus.REVIEW)
        await service.update_document(
            id=doc.id,
            data=update,
            company_id=company.id,
            db=test_session,
            user_id=None,
        )

        # Assert - status log was created
        stmt = select(DocumentStatusLog).where(DocumentStatusLog.document_id == doc.id)
        result = await test_session.execute(stmt)
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].from_status == DocumentStatus.DRAFT
        assert logs[0].to_status == DocumentStatus.REVIEW

    @pytest.mark.asyncio
    async def test_status_change_triggers_analysis(
        self, test_session: AsyncSession
    ):
        """Should trigger pattern analysis when status changes to approved."""
        # Arrange
        company = Company(name="Trigger Company", inn="7701000008", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1, status=DocumentStatus.REVIEW)
        ver = await _create_test_version(test_session, doc.id)
        await _create_test_section(
            test_session, ver.id, "Основной раздел", 1, 1,
            "Настоящий документ устанавливает правила."
        )
        await _create_test_term(test_session, doc.id, "Термин", "Определение")

        service = DocumentService()

        # Act
        update = DocumentUpdate(status=DocumentStatus.APPROVED)
        await service.update_document(
            id=doc.id,
            data=update,
            company_id=company.id,
            db=test_session,
            user_id=None,
        )

        # Assert
        await test_session.refresh(doc)
        assert doc.was_analyzed is True

        # Verify company was updated
        await test_session.refresh(company)
        assert company.document_structure is not None
        assert company.style_settings is not None
        assert company.style_settings.get("documents_analyzed") == 1

    @pytest.mark.asyncio
    async def test_no_log_on_same_status(
        self, test_session: AsyncSession
    ):
        """Should not create a log entry if status didn't change."""
        # Arrange
        company = Company(name="SameStatus Company", inn="7701000009", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        doc = await _create_test_document(test_session, company.id, 1, status=DocumentStatus.DRAFT)

        service = DocumentService()

        # Act - update with same status
        update = DocumentUpdate(status=DocumentStatus.DRAFT)
        await service.update_document(
            id=doc.id,
            data=update,
            company_id=company.id,
            db=test_session,
            user_id=None,
        )

        # Assert - no log should exist
        stmt = select(DocumentStatusLog).where(DocumentStatusLog.document_id == doc.id)
        result = await test_session.execute(stmt)
        logs = result.scalars().all()
        assert len(logs) == 0
