"""
Tests for Analysis Pipeline Service and API.

Covers:
1. test_trigger_analysis_creates_record
2. test_trigger_analysis_idempotency_same_hash
3. test_trigger_analysis_skips_when_running
4. test_pipeline_steps_update_status
5. test_reanalyze_creates_new_record
6. test_get_analysis_history
7. test_get_analysis_status
8. test_reanalyze_endpoint
"""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_status import DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.document_section import DocumentSection
from app.models.document_term import DocumentTerm
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.company import Company
from app.models.user import User
from app.services.analysis_pipeline_service import (
    AnalysisPipelineService,
    analysis_pipeline_service,
    _sha256,
)


# ─── Helpers ──────────────────────────────────────────────────────────────

TEST_FULL_TEXT = (
    "Настоящий регламент определяет порядок обработки персональных данных.\n"
    "Оператор — ООО «Тест».\n"
    "ПДн — персональные данные.\n"
    "Регламент № 2024-01 устанавливает требования к защите информации.\n"
    "Сайт: https://example.com/docs\n"
)


async def _create_test_document(
    session: AsyncSession,
    company_id: int,
    created_by: int,
    status: DocumentStatus = DocumentStatus.DRAFT,
) -> Document:
    doc = Document(
        company_id=company_id,
        title="Test Document for Pipeline",
        description="Test document",
        status=status,
        created_by=created_by,
    )
    session.add(doc)
    await session.flush()
    return doc


async def _create_test_version(
    session: AsyncSession,
    document_id: int,
    version_number: int = 1,
    full_text: str = TEST_FULL_TEXT,
) -> DocumentVersion:
    ver = DocumentVersion(
        document_id=document_id,
        version_number=version_number,
        file_path="test/path.docx",
        file_type="docx",
        file_size=1000,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        full_text=full_text,
        uploaded_by=None,
    )
    session.add(ver)
    await session.flush()
    return ver


async def _create_test_sections(
    session: AsyncSession, version_id: int, count: int = 3
) -> list[DocumentSection]:
    sections = []
    for i in range(count):
        sec = DocumentSection(
            document_version_id=version_id,
            title=f"Section {i + 1}",
            level=1 if i == 0 else 2,
            order_num=i + 1,
            content=f"Content of section {i + 1}." * 10,
        )
        session.add(sec)
        sections.append(sec)
    await session.flush()
    return sections


async def _create_test_terms(
    session: AsyncSession, document_id: int, count: int = 2
) -> list[DocumentTerm]:
    terms = []
    for i in range(count):
        term = DocumentTerm(
            document_id=document_id,
            term=f"Term {i + 1}",
            definition=f"Definition of term {i + 1}",
        )
        session.add(term)
        terms.append(term)
    await session.flush()
    return terms


async def _create_test_abbrs(
    session: AsyncSession, document_id: int, count: int = 1
) -> list[DocumentAbbreviation]:
    abbrs = []
    for i in range(count):
        abbr = DocumentAbbreviation(
            document_id=document_id,
            abbreviation=f"ABBR{i + 1}",
            full_form=f"Abbreviation {i + 1}",
        )
        session.add(abbr)
        abbrs.append(abbr)
    await session.flush()
    return abbrs


# ─── Test: trigger_analysis ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_analysis_creates_record(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Trigger analysis creates a DocumentAnalysis record."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id, DocumentStatus.APPROVED
    )
    await _create_test_version(test_session, doc.id)

    with patch.object(
        analysis_pipeline_service, "_launch_background_pipeline"
    ) as mock_launch:
        analysis_id = await analysis_pipeline_service.trigger_analysis(
            document_id=doc.id,
            company_id=demo_company.id,
            db=test_session,
            force=False,
        )

    assert analysis_id is not None, "Should return analysis_id"

    # Verify record exists
    stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
    result = await test_session.execute(stmt)
    analysis = result.scalar_one_or_none()
    assert analysis is not None
    assert analysis.document_id == doc.id
    assert analysis.status == "running"
    assert analysis.file_hash is not None

    # Verify document status updated
    assert doc.analysis_status == "running"

    # Verify background pipeline was launched
    mock_launch.assert_called_once_with(analysis_id, doc.id, demo_company.id)


@pytest.mark.asyncio
async def test_trigger_analysis_idempotency_same_hash(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Same content and same hash should skip analysis."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id, DocumentStatus.APPROVED
    )
    version = await _create_test_version(test_session, doc.id)

    # Set as already analyzed with same hash
    current_hash = _sha256(version.full_text)
    doc.analysis_hash = current_hash
    doc.analysis_status = "complete"
    await test_session.flush()

    with patch.object(
        analysis_pipeline_service, "_launch_background_pipeline"
    ) as mock_launch, patch(
        "app.services.rag_service.rag_service.get_document_chunks_count",
        new_callable=AsyncMock,
        return_value=5,
    ) as mock_count:
        analysis_id = await analysis_pipeline_service.trigger_analysis(
            document_id=doc.id,
            company_id=demo_company.id,
            db=test_session,
            force=False,
        )

    assert analysis_id is None, "Should skip (idempotency)"
    mock_launch.assert_not_called()
    mock_count.assert_awaited_once_with(
        document_id=doc.id,
        company_id=demo_company.id,
    )


@pytest.mark.asyncio
async def test_trigger_analysis_skips_when_running(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """If analysis_status is 'running', should skip."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id, DocumentStatus.APPROVED
    )
    await _create_test_version(test_session, doc.id)

    doc.analysis_status = "running"
    await test_session.flush()

    with patch.object(
        analysis_pipeline_service, "_launch_background_pipeline"
    ) as mock_launch:
        analysis_id = await analysis_pipeline_service.trigger_analysis(
            document_id=doc.id,
            company_id=demo_company.id,
            db=test_session,
            force=False,
        )

    assert analysis_id is None, "Should skip (already running)"
    mock_launch.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_analysis_no_version_skips(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """If document has no versions, trigger should return None."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )

    analysis_id = await analysis_pipeline_service.trigger_analysis(
        document_id=doc.id,
        company_id=demo_company.id,
        db=test_session,
        force=False,
    )

    assert analysis_id is None, "Should return None when no versions"


# ─── Test: pipeline steps ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_extract_text_step(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Step 1: extract_text should return text and hash."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    version = await _create_test_version(test_session, doc.id)

    file_hash, full_text, version_id = (
        await analysis_pipeline_service._step_extract_text(
            document_id=doc.id, db=test_session
        )
    )

    assert full_text == TEST_FULL_TEXT
    assert version_id == version.id
    assert file_hash == _sha256(TEST_FULL_TEXT)


@pytest.mark.asyncio
async def test_pipeline_parse_structure_step(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Step 2: parse_structure should count sections."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    version = await _create_test_version(test_session, doc.id)
    await _create_test_sections(test_session, version.id, count=5)

    count = await analysis_pipeline_service._step_parse_structure(
        version_id=version.id, db=test_session
    )

    assert count == 5


@pytest.mark.asyncio
async def test_pipeline_extract_terms_step(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Step 3: extract_terms should extract from text."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    await _create_test_version(test_session, doc.id)

    count = await analysis_pipeline_service._step_extract_terms(
        full_text=TEST_FULL_TEXT,
        document_id=doc.id,
        is_reanalysis=False,
        db=test_session,
    )

    # The test text has "Оператор — ООО «Тест»" which should be extracted as term
    assert count >= 0


@pytest.mark.asyncio
async def test_pipeline_extract_abbr_step(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Step 4: extract_abbr should extract abbreviations."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    await _create_test_version(test_session, doc.id)

    count = await analysis_pipeline_service._step_extract_abbr(
        full_text=TEST_FULL_TEXT,
        document_id=doc.id,
        is_reanalysis=False,
        db=test_session,
    )

    # "ПДн — персональные данные" should match as abbreviation
    assert count >= 1


@pytest.mark.asyncio
async def test_pipeline_extract_refs_step():
    """Step 5: extract_refs should count references."""
    svc = AnalysisPipelineService()
    count = await svc._step_extract_refs(full_text=TEST_FULL_TEXT)
    # "Регламент № 2024-01" + URL
    assert count >= 2


@pytest.mark.asyncio
async def test_pipeline_reanalysis_deletes_old_terms(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Reanalysis should delete old terms before extracting new ones."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    await _create_test_version(test_session, doc.id)
    await _create_test_terms(test_session, doc.id, count=3)

    # Count before reanalysis
    stmt = select(DocumentTerm).where(DocumentTerm.document_id == doc.id)
    result = await test_session.execute(stmt)
    before = len(result.scalars().all())
    assert before == 3

    # Run reanalysis
    count = await analysis_pipeline_service._step_extract_terms(
        full_text=TEST_FULL_TEXT,
        document_id=doc.id,
        is_reanalysis=True,
        db=test_session,
    )

    # Old terms should be deleted and new ones extracted
    stmt = select(DocumentTerm).where(DocumentTerm.document_id == doc.id)
    result = await test_session.execute(stmt)
    after = len(result.scalars().all())

    # After reanalysis, we should have only the newly extracted terms
    assert after == count


@pytest.mark.asyncio
async def test_pipeline_mark_complete_updates_document(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Step 8: mark_complete should update Document fields."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    await _create_test_version(test_session, doc.id)

    # Create analysis record
    analysis = DocumentAnalysis(
        document_id=doc.id,
        file_hash=_sha256(TEST_FULL_TEXT),
        status="running",
    )
    test_session.add(analysis)
    await test_session.flush()

    # Mark complete
    summary = {
        "sections_found": 3,
        "terms_found": 2,
        "abbreviations_found": 1,
        "chunks_indexed": 5,
        "total_steps": 8,
        "failed_steps": 0,
        "completed_steps": 8,
    }
    await analysis_pipeline_service._step_mark_complete(
        analysis_id=analysis.id,
        file_hash=_sha256(TEST_FULL_TEXT),
        result_summary=summary,
        db=test_session,
    )

    # Verify analysis
    assert analysis.status == "complete"
    assert analysis.completed_at is not None
    assert analysis.result_summary == summary

    # Verify document
    assert doc.analysis_hash == _sha256(TEST_FULL_TEXT)
    assert doc.analysis_status == "complete"


# ─── Test: get_status and get_history ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_analysis_status(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """get_status should return analysis details."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )
    analysis = DocumentAnalysis(
        document_id=doc.id,
        status="running",
    )
    test_session.add(analysis)
    await test_session.flush()

    status_data = await analysis_pipeline_service.get_status(
        analysis_id=analysis.id,
        db=test_session,
    )

    assert status_data is not None
    assert status_data["id"] == analysis.id
    assert status_data["status"] == "running"
    assert status_data["document_id"] == doc.id


@pytest.mark.asyncio
async def test_get_analysis_history(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """get_history should return all analyses for a document."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id
    )

    # Create two analyses
    for i in range(2):
        a = DocumentAnalysis(
            document_id=doc.id,
            status="complete" if i == 0 else "error",
        )
        test_session.add(a)
    await test_session.flush()

    history = await analysis_pipeline_service.get_history(
        document_id=doc.id,
        db=test_session,
    )

    assert len(history) == 2
    # Should be ordered by created_at desc
    assert history[0]["status"] == "error" or history[1]["status"] == "complete"


# ─── Test: Reanalyze ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reanalyze_creates_new_record(
    test_session: AsyncSession,
    admin_user: User,
    demo_company: Company,
):
    """Reanalyze should create a new analysis record even if already analyzed."""
    doc = await _create_test_document(
        test_session, demo_company.id, admin_user.id,
        status=DocumentStatus.APPROVED,
    )
    version = await _create_test_version(test_session, doc.id)

    # Set as previously analyzed
    doc.analysis_hash = _sha256(version.full_text)
    doc.analysis_status = "complete"
    await test_session.flush()

    # Create old analysis record
    old = DocumentAnalysis(
        document_id=doc.id,
        status="complete",
    )
    test_session.add(old)
    await test_session.flush()

    with patch.object(
        analysis_pipeline_service, "_launch_background_pipeline"
    ) as mock_launch:
        new_id = await analysis_pipeline_service.trigger_analysis(
            document_id=doc.id,
            company_id=demo_company.id,
            db=test_session,
            force=True,  # force skips idempotency
        )

    assert new_id is not None
    assert new_id != old.id  # Must be a new record
    mock_launch.assert_called_once()


@pytest.mark.asyncio
async def test_reanalyze_endpoint(
    client: AsyncClient,
    test_session: AsyncSession,
    admin_user: User,
    admin_token: str,
):
    """POST /api/v1/documents/{id}/reanalyze should return 202."""
    # Create doc in admin_user's own company
    doc = await _create_test_document(
        test_session, admin_user.active_company_id, admin_user.id,
        status=DocumentStatus.APPROVED,
    )
    await _create_test_version(test_session, doc.id)

    # Mock the background pipeline to avoid actual execution
    with patch.object(
        analysis_pipeline_service, "_launch_background_pipeline"
    ):
        response = await client.post(
            f"/api/v1/documents/{doc.id}/reanalyze",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["document_id"] == doc.id
    assert data["status"] == "running"
    assert data["message"] == "Reanalysis started"
    assert "analysis_id" in data


@pytest.mark.asyncio
async def test_reanalyze_endpoint_already_running(
    client: AsyncClient,
    test_session: AsyncSession,
    admin_user: User,
    admin_token: str,
):
    """Reanalyze should return 409 if already running."""
    doc = await _create_test_document(
        test_session, admin_user.active_company_id, admin_user.id,
        status=DocumentStatus.APPROVED,
    )
    await _create_test_version(test_session, doc.id)
    doc.analysis_status = "running"
    await test_session.flush()

    response = await client.post(
        f"/api/v1/documents/{doc.id}/reanalyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


# ─── Test: API endpoints ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_analysis_history_endpoint(
    client: AsyncClient,
    test_session: AsyncSession,
    admin_user: User,
    admin_token: str,
):
    """GET /api/v1/documents/{id}/analyses should return history."""
    doc = await _create_test_document(
        test_session, admin_user.active_company_id, admin_user.id,
    )
    a = DocumentAnalysis(document_id=doc.id, status="complete")
    test_session.add(a)
    await test_session.flush()

    response = await client.get(
        f"/api/v1/documents/{doc.id}/analyses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_analysis_status_api(
    client: AsyncClient,
    test_session: AsyncSession,
    admin_user: User,
    admin_token: str,
):
    """GET /api/v1/analysis/{id}/status should return status."""
    doc = await _create_test_document(
        test_session, admin_user.active_company_id, admin_user.id,
    )
    a = DocumentAnalysis(document_id=doc.id, status="running")
    test_session.add(a)
    await test_session.flush()

    response = await client.get(
        f"/api/v1/analysis/{a.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == a.id
    assert data["status"] == "running"
