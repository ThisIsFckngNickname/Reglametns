"""
Tests for Increment C: Document Generator + GigaChat Pro.

Coverage:
- Mock mode generation
- Generation with drafts
- Generation with influencing documents
- Prompt builder correctness
- Docx builder output
- JSON response parsing (valid, markdown-wrapped, malformed)
- API endpoint integration
"""

import json
import os
import tempfile
from io import BytesIO
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import UploadFile as FastAPIUploadFile
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.document import Document
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.document_term import DocumentTerm
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding
from app.core.security import create_access_token
from app.core.rate_limiter import InMemoryRateLimiter, RateLimiter
from app.services.cache_service import CacheService
from app.services.email_service import ConsoleEmailService
from app.services.generator_service import GeneratorService
from app.services.gigachat_service import GigaChatClient, MOCK_RESPONSE
from app.services.llm_client import LLMClient
from app.services.prompt_builder import PromptBuilder, prompt_builder
from app.services.docx_builder import DocxBuilder, docx_builder
from app.config import settings

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ─── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test engine with all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh test session for each test."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with overridden dependencies."""

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.email_service = ConsoleEmailService()
    app.state.rate_limiter = RateLimiter(redis_service=None)
    app.state.rate_limiter._memory = InMemoryRateLimiter(max_attempts=100, window_seconds=1)
    app.state.cache_service = CacheService(redis_service=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def holding_with_all_fields(test_session: AsyncSession) -> Holding:
    """Create a holding with all generation fields set."""
    holding = Holding(
        name="Gost Holding",
        inn="7701123456",
        legal_form="ООО",
        document_structure={
            "sections": [
                "Общие положения",
                "Термины и определения",
                "Основная часть",
                "Заключительные положения",
            ]
        },
        style_settings={
            "font_name": "Times New Roman",
            "font_size": 14,
            "line_spacing": 1.5,
        },
        use_gost=True,
    )
    test_session.add(holding)
    await test_session.flush()
    return holding


@pytest_asyncio.fixture
async def admin_user_with_holding(test_session: AsyncSession, holding_with_all_fields: Holding) -> User:
    """Create an admin user with active holding."""
    user = User(email="admin@gost.ru", is_verified=True)
    test_session.add(user)
    await test_session.flush()
    uh = UserHolding(user_id=user.id, holding_id=holding_with_all_fields.id, role="admin")
    test_session.add(uh)
    user.active_holding_id = holding_with_all_fields.id
    await test_session.flush()
    return user


@pytest.fixture
def admin_token(admin_user_with_holding: User) -> str:
    """Generate an access token for the admin user."""
    return create_access_token(admin_user_with_holding.id)


# ─── Test 1: Mock mode generation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_mock_mode(test_session: AsyncSession, admin_user_with_holding: User):
    """Test that generator returns mock document when GigaChat is in mock mode."""
    # Use GigaChatClient explicitly — it will be in mock mode since credentials
    # are not configured in test environment
    service = GeneratorService(llm_client=GigaChatClient())
    assert service.llm.is_mock, "LLM should be in mock mode"

    result = await service.generate(
        context_description="Тестовый контекст для демо-режима",
        user=admin_user_with_holding,
        holding_id=admin_user_with_holding.active_holding_id,
        db=test_session,
    )

    assert result is not None
    assert result.title == "Документ: Тестовый контекст для демо-режима"
    assert result.status == "draft"
    assert result.stats.versions_count == 1
    assert result.stats.sections_count == 4
    assert result.stats.terms_count == 2
    assert result.stats.abbreviations_count == 2

    assert result.current_version is not None
    assert result.current_version.version_number == 1
    assert result.current_version.file_type == "docx"

    # Verify document exists in DB
    stmt = select(Document).where(Document.id == result.id)
    db_result = await test_session.execute(stmt)
    doc = db_result.scalar_one_or_none()
    assert doc is not None
    assert doc.title == "Документ: Тестовый контекст для демо-режима"

    # Verify terms were saved
    term_stmt = select(DocumentTerm).where(DocumentTerm.document_id == result.id)
    term_result = await test_session.execute(term_stmt)
    terms = term_result.scalars().all()
    assert len(terms) == 2

    # Verify abbreviations were saved
    abbr_stmt = select(DocumentAbbreviation).where(DocumentAbbreviation.document_id == result.id)
    abbr_result = await test_session.execute(abbr_stmt)
    abbrs = abbr_result.scalars().all()
    assert len(abbrs) == 2


# ─── Test 2: Mock generation via API endpoint ──────────────────────────────

@pytest.mark.asyncio
async def test_generate_api_mock(client: AsyncClient, admin_token: str):
    """Test the /api/v1/generator/generate endpoint in mock mode."""
    response = await client.post(
        "/api/v1/generator/generate",
        data={
            "context": "Тестовый контекст для генерации документа",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Документ: Тестовый контекст для генерации документа"
    assert data["status"] == "draft"
    assert data["stats"]["versions_count"] == 1
    assert data["stats"]["sections_count"] == 4


# ─── Test 3: Generation with draft files ──────────────────────────────────

@pytest.mark.asyncio
async def test_generate_with_drafts(test_session: AsyncSession, admin_user_with_holding: User):
    """Test generation with uploaded draft files."""
    service = GeneratorService()

    # Create a mock draft file
    draft_content = "Это черновик документа.\nРаздел 1: Введение.\nРаздел 2: Основная часть.".encode("utf-8")
    draft_file = FastAPIUploadFile(
        filename="draft.txt",
        file=BytesIO(draft_content),
    )

    result = await service.generate(
        context_description="Тестовый контекст",
        user=admin_user_with_holding,
        holding_id=admin_user_with_holding.active_holding_id,
        draft_files=[draft_file],
        db=test_session,
    )

    assert result is not None
    assert result.title == "Документ: Тестовый контекст"
    assert result.status == "draft"


# ─── Test 4: Generation with influencing documents ─────────────────────────

@pytest.mark.asyncio
async def test_generate_with_influencing_docs(test_session: AsyncSession, admin_user_with_holding: User):
    """Test generation with influencing document IDs."""
    service = GeneratorService()

    # Create a document that will be an influencing document
    influencing_doc = Document(
        holding_id=admin_user_with_holding.active_holding_id,
        title="Политика конфиденциальности",
        description="Документ о защите данных",
        status="approved",
        created_by=admin_user_with_holding.id,
    )
    test_session.add(influencing_doc)
    await test_session.flush()

    result = await service.generate(
        context_description="Тестовый контекст",
        user=admin_user_with_holding,
        holding_id=admin_user_with_holding.active_holding_id,
        influencing_document_ids=[influencing_doc.id],
        db=test_session,
    )

    assert result is not None
    assert result.status == "draft"


# ─── Test 5: Prompt builder ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_builder(holding_with_all_fields: Holding):
    """Test that PromptBuilder generates correct system and user messages."""
    messages = prompt_builder.build_messages(
        holding=holding_with_all_fields,
        context_description="Новый регламент для отдела кадров",
        drafts_content="Черновик: правила найма сотрудников",
        terms=[{"term": "Регламент", "definition": "Нормативный документ"}],
        influencing_docs=[
            {"title": "Трудовой кодекс РФ", "source": "Федеральный закон"},
        ],
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    system_content = messages[0]["content"]
    user_content = messages[1]["content"]

    # System prompt should contain holding info
    assert "Gost Holding" in system_content
    assert "ООО" in system_content
    assert "ГОСТ Р 7.0.97-2016" in system_content
    assert "Трудовой кодекс РФ" in system_content
    assert "Регламент" in system_content

    # User prompt should contain context and drafts
    assert "Новый регламент для отдела кадров" in user_content
    assert "Черновик: правила найма сотрудников" in user_content


# ─── Test 6: Prompt builder without GOST ──────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_builder_no_gost(test_session: AsyncSession):
    """Test prompt builder with GOST disabled."""
    holding = Holding(
        name="Simple Holding",
        inn="7701123456",
        legal_form="АО",
        use_gost=False,
    )
    test_session.add(holding)
    await test_session.flush()

    messages = prompt_builder.build_messages(
        holding=holding,
        context_description="Простой контекст",
        drafts_content=None,
        terms=[],
        influencing_docs=[],
    )

    system_content = messages[0]["content"]
    assert "ГОСТ Р 7.0.97-2016" not in system_content
    assert "Simple Holding" in system_content
    assert "АО" in system_content


# ─── Test 7: Docx builder output ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_docx_builder(test_session: AsyncSession, holding_with_all_fields: Holding):
    """Test that DocxBuilder creates a valid .docx file with correct structure."""
    result = {
        "title": "Тестовый регламент",
        "description": "Описание тестового регламента",
        "sections": [
            {
                "title": "1. Общие положения",
                "level": 1,
                "content": "Текст общих положений.",
                "subsections": [
                    {
                        "title": "1.1. Цели",
                        "level": 2,
                        "content": "Цели регламента.",
                    }
                ],
            }
        ],
        "terms": [
            {"term": "Регламент", "definition": "Нормативный документ"},
        ],
        "abbreviations": [
            {"abbreviation": "ООО", "full_form": "Общество с ограниченной ответственностью"},
        ],
        "references": [
            {"title": "Конституция РФ", "source": "12.12.1993"},
        ],
    }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        output_path = tmp.name

    try:
        result_path = docx_builder.build(result, holding_with_all_fields, output_path)

        assert result_path == output_path
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

        # Verify it's a valid .docx by reading it back
        from docx import Document as DocxDocument
        doc = DocxDocument(output_path)
        # Should have content
        assert len(doc.paragraphs) > 0
        # Title should be present
        titles = [p.text for p in doc.paragraphs if "Тестовый регламент" in p.text]
        assert len(titles) > 0
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


# ─── Test 8: Docx builder with GOST ──────────────────────────────────────

@pytest.mark.asyncio
async def test_docx_builder_gost(test_session: AsyncSession):
    """Test DocxBuilder with GOST enabled holding."""
    holding = Holding(
        name="Gost Holding",
        inn="7701123456",
        legal_form="ООО",
        use_gost=True,
    )
    test_session.add(holding)
    await test_session.flush()

    result = {
        "title": "GOST Регламент",
        "description": "Описание",
        "sections": [],
        "terms": [],
        "abbreviations": [],
        "references": [],
    }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        output_path = tmp.name

    try:
        docx_builder.build(result, holding, output_path)
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

        # Verify margins (GOST: left=3cm, right=1.5cm, top=2cm, bottom=2cm)
        from docx import Document as DocxDocument
        doc = DocxDocument(output_path)
        section = doc.sections[0]
        from docx.shared import Cm
        assert abs(section.left_margin - Cm(3.0)) < 100000  # EMU tolerance
        assert abs(section.right_margin - Cm(1.5)) < 100000
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


# ─── Test 9: Parse response — valid JSON ──────────────────────────────────

@pytest.mark.asyncio
async def test_parse_response_valid_json():
    """Test parsing of a valid JSON response."""
    service = GeneratorService()
    valid_json = json.dumps(MOCK_RESPONSE, ensure_ascii=False)
    result = await service._parse_response(valid_json)
    assert result["title"] == MOCK_RESPONSE["title"]
    assert len(result["sections"]) == 4
    assert len(result["terms"]) == 2


# ─── Test 10: Parse response — markdown wrapped JSON ──────────────────────

@pytest.mark.asyncio
async def test_parse_response_markdown_wrapped():
    """Test parsing of JSON wrapped in markdown code block."""
    service = GeneratorService()
    markdown_response = "```json\n" + json.dumps(MOCK_RESPONSE, ensure_ascii=False) + "\n```"
    result = await service._parse_response(markdown_response)
    assert result["title"] == MOCK_RESPONSE["title"]
    assert len(result["sections"]) == 4


# ─── Test 11: Parse response — malformed JSON with fallback ──────────────

@pytest.mark.asyncio
async def test_parse_response_malformed_json():
    """Test that malformed JSON raises an error."""
    service = GeneratorService()
    with pytest.raises(Exception) as excinfo:
        await service._parse_response("Это не JSON { сломанный")
    assert "GENERATION_FAILED" in str(excinfo.value) or "Не удалось" in str(excinfo.value)


# ─── Test 12: Parse response — empty string ───────────────────────────────

@pytest.mark.asyncio
async def test_parse_response_empty():
    """Test parsing of empty response uses mock fallback."""
    service = GeneratorService()
    result = await service._parse_response("")
    assert result["title"] == MOCK_RESPONSE["title"]


# ─── Test 13: Extract draft text from .txt ────────────────────────────────

@pytest.mark.asyncio
async def test_extract_draft_text():
    """Test extraction of text from draft files."""
    service = GeneratorService()
    content = "Test draft content\nLine 2\nLine 3".encode("utf-8")
    draft_file = FastAPIUploadFile(
        filename="draft.txt",
        file=BytesIO(content),
    )
    result = await service._extract_draft_text([draft_file])
    assert "Test draft content" in result
    assert "draft.txt" in result


# ─── Test 14: GigaChat client mock mode ──────────────────────────────────

@pytest.mark.asyncio
async def test_gigachat_client_mock_mode():
    """Test that GigaChatClient returns mock response in mock mode."""
    client = GigaChatClient()
    assert client.is_mock

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "test"}]
    )
    parsed = json.loads(response)
    assert parsed["title"] == MOCK_RESPONSE["title"]


# ─── Test 15: Full API integration with influencing docs ──────────────────

@pytest.mark.asyncio
async def test_generate_api_with_influencing_docs(
    client: AsyncClient,
    admin_token: str,
    admin_user_with_holding: User,
    test_session: AsyncSession,
):
    """Test the API endpoint with influencing documents."""
    # Create an influencing document first
    doc = Document(
        holding_id=admin_user_with_holding.active_holding_id,
        title="Влияющий документ",
        description="Тест",
        status="approved",
        created_by=admin_user_with_holding.id,
    )
    test_session.add(doc)
    await test_session.flush()

    response = await client.post(
        "/api/v1/generator/generate",
        data={
            "context": "Тестовый контекст с влияющими документами",
            "influencing_document_ids": json.dumps([doc.id]),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"


# ─── Test 16: Auth required for generation ────────────────────────────────

@pytest.mark.asyncio
async def test_generate_requires_auth(client: AsyncClient):
    """Test that generation endpoint requires authentication."""
    response = await client.post(
        "/api/v1/generator/generate",
        data={"context": "Тест"},
    )
    assert response.status_code == 401


# ─── Test 17: Prompt builder with empty terms and docs ────────────────────

@pytest.mark.asyncio
async def test_prompt_builder_empty_data(holding_with_all_fields: Holding):
    """Test prompt builder with no terms and no influencing docs."""
    messages = prompt_builder.build_messages(
        holding=holding_with_all_fields,
        context_description="Контекст",
        drafts_content=None,
        terms=[],
        influencing_docs=[],
    )
    system_content = messages[0]["content"]
    assert "Термины не указаны" in system_content
    assert "Влияющие документы не указаны" in system_content
