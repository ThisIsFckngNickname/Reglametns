"""
Tests for GeneratorService V2 (generate_document) and PromptBuilder V2.

Coverage:
- PromptBuilder V2 system prompt formatting
- PromptBuilder V2 with various knowledge sources
- GeneratorService V2 generate_document with mocked LLM
- Generation with failed web search (non-blocking)
"""

import json
import os
import tempfile
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.company_term import CompanyTerm
from app.models.company_abbreviation import CompanyAbbreviation
from app.schemas.generator import GenerateRequestV2
from app.services.generator_service import generator_service
from app.services.prompt_builder import prompt_builder


# ─── PromptBuilder V2 Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_builder_v2_basic(test_session: AsyncSession):
    """PromptBuilder V2 builds correct system and user messages."""
    company = Company(
        name="Тестовый Холдинг",
        inn="7701123456",
        legal_form="ООО",
        document_structure="1. Общие положения\n2. Основная часть\n3. Заключительные положения",
    )
    test_session.add(company)
    await test_session.flush()

    messages = prompt_builder.build_messages_v2(
        company=company,
        topic="Регламент по горюче-смазочным материалам на предприятии",
        document_type="regulation",
        company_terms=[
            {"term": "ГСМ", "definition": "Горюче-смазочные материалы"},
            {"term": "МОЛ", "definition": "Материально-ответственное лицо"},
        ],
        company_abbreviations=[
            {"abbreviation": "ГСМ", "full_form": "Горюче-смазочные материалы"},
        ],
        similar_chunks=[
            {"text": "Настоящий регламент устанавливает порядок учёта.", "title": "Регламент учёта"},
        ],
        web_results_text="## Изученные источники\n1. Закон №...\n   URL: http://example.com",
        draft_text="Черновик: правила учёта ГСМ.",
        influencing_docs=[
            {"title": "Политика по ГСМ", "source": "Внутренний документ", "full_text": "Текст политики..."},
        ],
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    system_content = messages[0]["content"]
    user_content = messages[1]["content"]

    # System prompt checks
    assert "Тестовый Холдинг" in system_content
    assert "ООО" in system_content
    assert "Регламент" in system_content
    assert "ГСМ" in system_content
    assert "Горюче-смазочные материалы" in system_content
    assert "МОЛ" in system_content
    assert "Настоящий регламент устанавливает" in system_content
    assert "Закон №" in system_content
    assert "Политика по ГСМ" in system_content

    # User prompt checks
    assert "ГСМ" in user_content
    assert "Черновик: правила учёта ГСМ" in user_content


@pytest.mark.asyncio
async def test_prompt_builder_v2_empty_sources(test_session: AsyncSession):
    """PromptBuilder V2 handles empty sources gracefully."""
    company = Company(name="Test", inn="7701123456", legal_form="АО")
    test_session.add(company)
    await test_session.flush()

    messages = prompt_builder.build_messages_v2(
        company=company,
        topic="Тестовая тема для документа длиной более двадцати символов",
        document_type="order",
        company_terms=[],
        company_abbreviations=[],
        similar_chunks=[],
        web_results_text=None,
        draft_text="",
        influencing_docs=[],
    )

    system_content = messages[0]["content"]
    assert "Термины холдинга не определены" in system_content
    assert "Сокращения холдинга не определены" in system_content
    assert "Похожие документы не найдены" in system_content
    assert "Поиск в интернете не выполнялся" in system_content
    assert "Влияющие документы не указаны" in system_content


@pytest.mark.asyncio
async def test_prompt_builder_v2_document_types():
    """PromptBuilder V2 handles different document types."""
    company = Company(id=1, name="Test", inn="7701123456", legal_form="ООО",
                      document_structure=None)

    for doc_type in ["regulation", "order", "provision", "policy", "directive"]:
        messages = prompt_builder.build_messages_v2(
            company=company,
            topic=f"Тестовая тема для типа {doc_type} с длиной более 20 символов",
            document_type=doc_type,
        )
        label = prompt_builder.get_document_type_label(doc_type)
        assert label in messages[0]["content"]


# ─── GeneratorService V2 Tests (mocked LLM) ──────────────────────────────

MOCK_LLM_RESPONSE = json.dumps({
    "title": "Тестовый регламент по ГСМ",
    "description": "Настоящий регламент устанавливает порядок учёта ГСМ.",
    "sections": [
        {
            "title": "1. Общие положения",
            "level": 1,
            "content": "1.1. Настоящий регламент определяет порядок учёта.",
            "subsections": [],
        }
    ],
    "terms": [{"term": "ГСМ", "definition": "Горюче-смазочные материалы"}],
    "abbreviations": [],
    "references": [],
})


@pytest.mark.asyncio
async def test_generate_document_v2(
    test_session: AsyncSession,
    admin_user: User,
):
    """Test generate_document with mocked LLM."""
    company = await test_session.get(Company, admin_user.active_company_id)
    assert company is not None

    # Pre-create a CompanyTerm for testing
    term = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="Горюче-смазочные материалы",
        is_manual=False,
    )
    test_session.add(term)
    await test_session.flush()

    mock_llm = AsyncMock()
    mock_llm.chat_completion = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    generator_service._llm_client = mock_llm

    result = await generator_service.generate_document(
        topic="Регламент по горюче-смазочным материалам длиной более 20 символов",
        company_id=admin_user.active_company_id,
        document_type="regulation",
        user_id=admin_user.id,
        search_enabled=False,
        db=test_session,
    )

    assert result is not None
    assert result.status == "draft"
    assert result.title == "Тестовый регламент по ГСМ"
    assert result.stats.terms_count >= 1


@pytest.mark.asyncio
async def test_generate_document_v2_with_failed_web_search(
    test_session: AsyncSession,
    admin_user: User,
):
    """Generation does NOT block when web search fails."""
    mock_llm = AsyncMock()
    mock_llm.chat_completion = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    generator_service._llm_client = mock_llm

    from app.services.web_search_service import web_search_service
    with patch.object(web_search_service, "enrich_prompt", side_effect=Exception("Web search error")):
        result = await generator_service.generate_document(
            topic="Регламент по горюче-смазочным материалам длиной более 20 символов",
            company_id=admin_user.active_company_id,
            document_type="regulation",
            user_id=admin_user.id,
            search_enabled=True,
            db=test_session,
        )

        assert result is not None
        assert result.status == "draft"


@pytest.mark.asyncio
async def test_generate_document_v2_with_draft_file(
    test_session: AsyncSession,
    admin_user: User,
):
    """Test generate_document with a draft file path."""
    # Create a temp draft file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Раздел 1: Введение\nРаздел 2: Основная часть\n")
        draft_path = f.name

    try:
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(return_value=MOCK_LLM_RESPONSE)
        generator_service._llm_client = mock_llm

        result = await generator_service.generate_document(
            topic="Регламент по горюче-смазочным материалам длиной более 20 символов",
            company_id=admin_user.active_company_id,
            document_type="regulation",
            user_id=admin_user.id,
            draft_file_path=draft_path,
            search_enabled=False,
            db=test_session,
        )

        assert result is not None
        assert result.status == "draft"
    finally:
        os.unlink(draft_path)


# ─── GenerateRequestV2 validation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_request_v2_validation():
    """Validate GenerateRequestV2 schema."""
    # Valid request
    req = GenerateRequestV2(
        topic="Регламент по горюче-смазочным материалам длиной более 20 символов",
        document_type="regulation",
        company_id=1,
    )
    assert req.topic is not None
    assert req.document_type == "regulation"
    assert req.search_enabled is True

    # Invalid document_type
    with pytest.raises(ValueError):
        GenerateRequestV2(
            topic="Тестовая тема длиной более 20 символов",
            document_type="invalid_type",
            company_id=1,
        )

    # Short topic
    with pytest.raises(ValueError):
        GenerateRequestV2(
            topic="Короткая",
            document_type="regulation",
            company_id=1,
        )


# ─── API endpoint test ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_v2_endpoint_requires_auth(client: AsyncClient):
    """POST /api/v1/generator/generate-v2 should return 401 without auth."""
    response = await client.post(
        "/api/v1/generator/generate-v2",
        json={
            "topic": "Регламент по горюче-смазочным материалам длиной более 20 символов",
            "document_type": "regulation",
            "company_id": 1,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_v2_endpoint_with_auth(
    client: AsyncClient,
    admin_token: str,
    admin_user: User,
    test_session: AsyncSession,
):
    """POST /api/v1/generator/generate-v2 returns 200 with mocked LLM."""
    mock_llm = AsyncMock()
    mock_llm.chat_completion = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    generator_service._llm_client = mock_llm

    response = await client.post(
        "/api/v1/generator/generate-v2",
        json={
            "topic": "Регламент по горюче-смазочным материалам длиной более 20 символов",
            "document_type": "regulation",
            "company_id": admin_user.active_company_id,
            "search_enabled": False,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"
    assert "title" in data


@pytest.mark.asyncio
async def test_generate_v2_endpoint_company_mismatch(
    client: AsyncClient,
    admin_token: str,
):
    """Company mismatch should return 403."""
    response = await client.post(
        "/api/v1/generator/generate-v2",
        json={
            "topic": "Регламент по горюче-смазочным материалам длиной более 20 символов",
            "document_type": "regulation",
            "company_id": 99999,  # Different from admin's active_company
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
