"""
Tests for pipeline integration with CompanyTerm/CompanyAbbreviation sync.

Coverage:
- _sync_terms_to_company inserts new terms
- _sync_abbreviations_to_company inserts new abbreviations
- _sync_terms_to_company skips existing terms with same definition
- _sync_terms_to_company skips existing terms with different definition
- _step_extract_terms calls sync (non-blocking)
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.company_term import CompanyTerm
from app.models.company_abbreviation import CompanyAbbreviation
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.document_status import DocumentStatus
from app.models.user import User
from app.services.analysis_pipeline_service import analysis_pipeline_service


TEST_FULL_TEXT = (
    "Настоящий регламент определяет порядок обработки персональных данных.\n"
    "Оператор — ООО «Тест».\n"
    "ПДн — персональные данные.\n"
)


@pytest.mark.asyncio
async def test_sync_terms_to_company_inserts_new(
    test_session: AsyncSession,
    admin_user: User,
):
    """_sync_terms_to_company inserts new terms."""
    terms_data = [
        {"term": "ГСМ", "definition": "Горюче-смазочные материалы"},
        {"term": "МОЛ", "definition": "Материально-ответственное лицо"},
    ]

    stats = await analysis_pipeline_service._sync_terms_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_terms=terms_data,
        db=test_session,
    )

    assert stats["inserted"] == 2
    assert stats["skipped_exists"] == 0
    assert stats["skipped_mismatch"] == 0

    # Verify in DB
    stmt = select(CompanyTerm).where(
        CompanyTerm.company_id == admin_user.active_company_id,
        CompanyTerm.term == "ГСМ",
    )
    result = await test_session.execute(stmt)
    term = result.scalar_one_or_none()
    assert term is not None
    assert term.definition == "Горюче-смазочные материалы"
    assert term.source_document_id == 1
    assert term.is_manual is False


@pytest.mark.asyncio
async def test_sync_terms_to_company_skips_existing(
    test_session: AsyncSession,
    admin_user: User,
):
    """_sync_terms_to_company skips existing terms with same definition."""
    # Pre-insert a term
    existing = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="Горюче-смазочные материалы",
        is_manual=False,
    )
    test_session.add(existing)
    await test_session.flush()

    terms_data = [
        {"term": "ГСМ", "definition": "Горюче-смазочные материалы"},
        {"term": "НОВЫЙ", "definition": "Новое определение"},
    ]

    stats = await analysis_pipeline_service._sync_terms_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_terms=terms_data,
        db=test_session,
    )

    assert stats["inserted"] == 1  # only НОВЫЙ
    assert stats["skipped_exists"] == 1  # ГСМ with same def
    assert stats["skipped_mismatch"] == 0


@pytest.mark.asyncio
async def test_sync_terms_to_company_skips_mismatch(
    test_session: AsyncSession,
    admin_user: User,
):
    """_sync_terms_to_company skips existing terms with different definition."""
    existing = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="Старое определение",
        is_manual=False,
    )
    test_session.add(existing)
    await test_session.flush()

    terms_data = [
        {"term": "ГСМ", "definition": "Новое определение"},
    ]

    stats = await analysis_pipeline_service._sync_terms_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_terms=terms_data,
        db=test_session,
    )

    assert stats["inserted"] == 0
    assert stats["skipped_exists"] == 0
    assert stats["skipped_mismatch"] == 1


@pytest.mark.asyncio
async def test_sync_abbreviations_to_company_inserts_new(
    test_session: AsyncSession,
    admin_user: User,
):
    """_sync_abbreviations_to_company inserts new abbreviations."""
    abbr_data = [
        {"abbreviation": "ГСМ", "full_form": "Горюче-смазочные материалы"},
        {"abbreviation": "МОЛ", "full_form": "Материально-ответственное лицо"},
    ]

    stats = await analysis_pipeline_service._sync_abbreviations_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_abbreviations=abbr_data,
        db=test_session,
    )

    assert stats["inserted"] == 2

    stmt = select(CompanyAbbreviation).where(
        CompanyAbbreviation.company_id == admin_user.active_company_id,
        CompanyAbbreviation.abbreviation == "ГСМ",
    )
    result = await test_session.execute(stmt)
    abbr = result.scalar_one_or_none()
    assert abbr is not None
    assert abbr.full_form == "Горюче-смазочные материалы"


@pytest.mark.asyncio
async def test_sync_abbreviations_to_company_skips_existing(
    test_session: AsyncSession,
    admin_user: User,
):
    """_sync_abbreviations_to_company skips existing with same full_form."""
    existing = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="ГСМ",
        full_form="Горюче-смазочные материалы",
        is_manual=False,
    )
    test_session.add(existing)
    await test_session.flush()

    abbr_data = [
        {"abbreviation": "ГСМ", "full_form": "Горюче-смазочные материалы"},
    ]

    stats = await analysis_pipeline_service._sync_abbreviations_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_abbreviations=abbr_data,
        db=test_session,
    )

    assert stats["inserted"] == 0
    assert stats["skipped_exists"] == 1


@pytest.mark.asyncio
async def test_sync_skips_empty_terms(
    test_session: AsyncSession,
    admin_user: User,
):
    """Empty terms/abbreviations should be skipped."""
    stats_terms = await analysis_pipeline_service._sync_terms_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_terms=[{"term": "", "definition": ""}],
        db=test_session,
    )
    assert stats_terms["inserted"] == 0

    stats_abbr = await analysis_pipeline_service._sync_abbreviations_to_company(
        company_id=admin_user.active_company_id,
        document_id=1,
        extracted_abbreviations=[{"abbreviation": "", "full_form": ""}],
        db=test_session,
    )
    assert stats_abbr["inserted"] == 0
