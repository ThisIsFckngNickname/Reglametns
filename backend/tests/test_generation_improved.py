"""
Tests for Increment 2: LLM abstraction, Ollama client, style patterns, detailed prompts.

Coverage:
1. LLMClient interface — abstract methods
2. GigaChatClient implements LLMClient
3. OllamaClient constructor and fallback
4. Prompt builder with style patterns
5. Generator service with new LLM abstraction
6. Style patterns formatting
7. Long document generation settings (max_tokens)
8. Generator service uses LLMClient interface
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
from app.services.ollama_client import OllamaClient, ollama_client
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
async def holding_with_patterns(test_session: AsyncSession) -> Holding:
    """Create a holding with style patterns from analysis."""
    holding = Holding(
        name="Pattern Holding",
        inn="7701123456",
        legal_form="ООО",
        document_structure={
            "sections": [
                "Общие положения",
                "Термины и определения",
                "Основная часть",
                "Заключительные положения",
            ],
            "max_depth": 2,
            "total_sections": 4,
            "top_level_titles": ["Общие положения", "Основная часть"],
        },
        style_settings={
            "typical_phrases": [
                "Настоящий документ устанавливает",
                "В соответствии с действующим законодательством",
                "Ответственность за выполнение возлагается",
            ],
            "avg_sentence_length": 12.5,
            "documents_analyzed": 3,
            "font_name": "Times New Roman",
            "font_size": 14,
        },
        use_gost=True,
    )
    test_session.add(holding)
    await test_session.flush()
    return holding


@pytest_asyncio.fixture
async def admin_user_with_holding(
    test_session: AsyncSession, holding_with_patterns: Holding
) -> User:
    """Create an admin user with active holding."""
    user = User(email="admin@patterns.ru", is_verified=True)
    test_session.add(user)
    await test_session.flush()
    uh = UserHolding(
        user_id=user.id, holding_id=holding_with_patterns.id, role="admin"
    )
    test_session.add(uh)
    user.active_holding_id = holding_with_patterns.id
    await test_session.flush()
    return user


# ─── Test 1: LLMClient is abstract ────────────────────────────────────────

class TestLLMClientInterface:
    """Tests for LLMClient abstract interface."""

    def test_llm_client_cannot_be_instantiated(self):
        """LLMClient should not be instantiable directly."""
        with pytest.raises(TypeError):
            LLMClient()  # type: ignore[abstract]

    def test_gigachat_client_implements_llm_client(self):
        """GigaChatClient should be a concrete implementation of LLMClient."""
        client = GigaChatClient()
        assert isinstance(client, LLMClient)
        assert hasattr(client, "is_mock")
        assert hasattr(client, "chat_completion")

    def test_ollama_client_implements_llm_client(self):
        """OllamaClient should be a concrete implementation of LLMClient."""
        client = OllamaClient()
        assert isinstance(client, LLMClient)
        assert hasattr(client, "is_mock")
        assert hasattr(client, "chat_completion")

    def test_ollama_client_default_state(self):
        """OllamaClient should start with is_mock=False."""
        client = OllamaClient()
        assert client.is_mock is False
        assert client.base_url == settings.ollama_base_url.rstrip("/")
        assert client.model == settings.ollama_model


# ─── Test 2: GeneratorService uses LLMClient ────────────────────────────

class TestGeneratorServiceAbstraction:
    """Tests for GeneratorService with LLMClient abstraction."""

    @pytest.mark.asyncio
    async def test_generator_accepts_custom_llm_client(self):
        """Generator should accept any LLMClient implementation."""
        # Create a mock LLM client
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.is_mock = True
        mock_client.chat_completion.return_value = json.dumps(
            MOCK_RESPONSE, ensure_ascii=False
        )

        service = GeneratorService(llm_client=mock_client)
        assert service.llm is mock_client
        assert service.llm.is_mock is True

    @pytest.mark.asyncio
    async def test_generator_fallback_to_gigachat(self):
        """Generator should use GigaChat when llm_provider is 'gigachat'."""
        original_provider = settings.llm_provider
        try:
            settings.llm_provider = "gigachat"
            service = GeneratorService()
            assert isinstance(service.llm, GigaChatClient)
        finally:
            settings.llm_provider = original_provider

    @pytest.mark.asyncio
    async def test_generator_uses_ollama_by_default(self):
        """Generator should use OllamaClient when llm_provider is 'ollama'."""
        original_provider = settings.llm_provider
        try:
            settings.llm_provider = "ollama"
            service = GeneratorService()
            assert isinstance(service.llm, OllamaClient)
        finally:
            settings.llm_provider = original_provider


# ─── Test 3: Prompt builder with style patterns ──────────────────────────

class TestPromptBuilderWithPatterns:
    """Tests for PromptBuilder with style patterns."""

    @pytest.mark.asyncio
    async def test_prompt_builder_includes_style_patterns(
        self, holding_with_patterns: Holding
    ):
        """Prompt should include style patterns when provided."""
        style_patterns_text = "Типичные фразы: «Настоящий документ устанавливает…» | Средняя длина предложения: ~12 слов."
        messages = prompt_builder.build_messages(
            holding=holding_with_patterns,
            context_description="Новый регламент",
            drafts_content=None,
            terms=[],
            influencing_docs=[],
            style_patterns=style_patterns_text,
        )

        system_content = messages[0]["content"]
        assert style_patterns_text in system_content
        assert "СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА" in system_content

    @pytest.mark.asyncio
    async def test_prompt_builder_without_style_patterns(
        self, holding_with_patterns: Holding
    ):
        """Prompt should handle missing style patterns gracefully."""
        messages = prompt_builder.build_messages(
            holding=holding_with_patterns,
            context_description="Новый регламент",
            drafts_content=None,
            terms=[],
            influencing_docs=[],
        )

        system_content = messages[0]["content"]
        # When no style_patterns provided, it should extract from holding
        assert "СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА" in system_content

    @pytest.mark.asyncio
    async def test_prompt_builder_detailed_template(
        self, holding_with_patterns: Holding
    ):
        """The system prompt should ask for a detailed 20-50 page document."""
        messages = prompt_builder.build_messages(
            holding=holding_with_patterns,
            context_description="Регламент закупок",
            drafts_content=None,
            terms=[],
            influencing_docs=[],
        )

        system_content = messages[0]["content"]
        assert "20-50 страниц" in system_content
        assert "5-10 предложений" in system_content
        assert "ОБЪЁМНЫМ" in system_content
        assert "НЕ ИСПОЛЬЗУЙ шаблонные фразы" in system_content

    @pytest.mark.asyncio
    async def test_prompt_builder_generated_with_style_patterns(
        self, holding_with_patterns: Holding
    ):
        """Test that _format_style_patterns generates proper text."""
        patterns = prompt_builder._format_style_patterns(
            holding_with_patterns.style_settings
        )
        assert "Типичные фразы" in patterns
        assert "Настоящий документ устанавливает" in patterns
        assert "Средняя длина предложения" in patterns
        assert "Проанализировано документов" in patterns

    @pytest.mark.asyncio
    async def test_format_style_patterns_empty(self):
        """Test _format_style_patterns with None/empty input."""
        result = prompt_builder._format_style_patterns(None)
        assert result == "Стилистические паттерны не обнаружены."

        result = prompt_builder._format_style_patterns({})
        assert result == "Стилистические паттерны не обнаружены."

        result = prompt_builder._format_style_patterns({"other": "data"})
        assert result == "Стилистические паттерны не обнаружены."


# ─── Test 4: GeneratorService._format_style_patterns_for_prompt ──────────

class TestStylePatternsForPrompt:
    """Tests for GeneratorService style patterns formatting."""

    def test_format_with_phrases(self):
        """Should format typical phrases correctly."""
        service = GeneratorService()
        result = service._format_style_patterns_for_prompt({
            "typical_phrases": ["Фраза один", "Фраза два"],
            "avg_sentence_length": 10.5,
        })
        assert "Типичные фразы" in result
        assert "Фраза один" in result
        assert "Фраза два" in result
        assert "~10.5" in result

    def test_format_empty(self):
        """Should return empty string for empty/None input."""
        service = GeneratorService()
        assert service._format_style_patterns_for_prompt(None) == ""
        assert service._format_style_patterns_for_prompt({}) == ""

    def test_format_no_phrases(self):
        """Should handle missing phrases gracefully."""
        service = GeneratorService()
        result = service._format_style_patterns_for_prompt({
            "avg_sentence_length": 15.0,
        })
        assert "~15.0" in result


# ─── Test 5: GeneratorService uses custom LLM for generation ────────────

class TestGeneratorWithCustomLLM:
    """Tests for GeneratorService with a custom LLM client."""

    @pytest.mark.asyncio
    async def test_generate_with_mock_llm(
        self, test_session: AsyncSession, admin_user_with_holding: User
    ):
        """Generator should work with a mock LLM client (full pipeline)."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.is_mock = True
        mock_llm.chat_completion.return_value = json.dumps(
            MOCK_RESPONSE, ensure_ascii=False
        )

        service = GeneratorService(llm_client=mock_llm)

        result = await service.generate(
            context_description="Тестовый контекст с mock LLM",
            user=admin_user_with_holding,
            holding_id=admin_user_with_holding.active_holding_id,
            db=test_session,
        )

        assert result is not None
        assert result.status == "draft"
        assert result.title == "Документ: Тестовый контекст с mock LLM"
        mock_llm.chat_completion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_llm_fallback_on_error(
        self, test_session: AsyncSession, admin_user_with_holding: User
    ):
        """Generator should fall back to mock if LLM raises an exception."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.is_mock = False
        mock_llm.chat_completion.side_effect = RuntimeError("LLM failed")

        service = GeneratorService(llm_client=mock_llm)

        result = await service.generate(
            context_description="Падающий LLM",
            user=admin_user_with_holding,
            holding_id=admin_user_with_holding.active_holding_id,
            db=test_session,
        )

        assert result is not None
        assert result.status == "draft"
        # Should use context_description for title since it fell back to mock
        assert "Падающий LLM" in result.title
        mock_llm.chat_completion.assert_awaited_once()


# ─── Test 6: Long document generation settings ──────────────────────────

class TestLongDocumentSettings:
    """Tests for long document generation settings."""

    def test_default_max_tokens_increased(self):
        """Default max_tokens should be 48000 for long documents."""
        assert settings.generation_max_tokens == 48000

    def test_gigachat_uses_high_max_tokens(self):
        """GigaChatClient should support high max_tokens."""
        client = GigaChatClient()
        # The mock mode doesn't use max_tokens, but the method signature accepts it
        # Just verify the method exists and accepts the param
        import inspect
        sig = inspect.signature(client.chat_completion)
        assert "max_tokens" in sig.parameters
        param = sig.parameters["max_tokens"]
        assert param.default == 48000

    def test_ollama_uses_high_max_tokens(self):
        """OllamaClient should support high max_tokens via num_predict."""
        client = OllamaClient()
        import inspect
        sig = inspect.signature(client.chat_completion)
        assert "max_tokens" in sig.parameters
        param = sig.parameters["max_tokens"]
        assert param.default == 48000

    def test_llm_client_abstract_uses_high_max_tokens(self):
        """LLMClient abstract should have 48000 default max_tokens."""
        import inspect
        sig = inspect.signature(LLMClient.chat_completion)
        assert "max_tokens" in sig.parameters
        param = sig.parameters["max_tokens"]
        assert param.default == 48000


# ─── Test 7: Maximum tokens consistency ─────────────────────────────────

class TestMaxTokensConfig:
    """Tests for max_tokens configuration consistency."""

    def test_generation_max_tokens_config(self):
        """Settings should expose generation_max_tokens."""
        assert hasattr(settings, "generation_max_tokens")
        assert settings.generation_max_tokens >= 32000

    def test_temperature_config(self):
        """Settings should have generation_temperature."""
        assert hasattr(settings, "generation_temperature")
        assert 0.0 <= settings.generation_temperature <= 1.0

    def test_llm_provider_config(self):
        """Settings should have llm_provider."""
        assert hasattr(settings, "llm_provider")
        assert settings.llm_provider in ("ollama", "gigachat", "mock")

    def test_ollama_settings(self):
        """Settings should have ollama config."""
        assert hasattr(settings, "ollama_base_url")
        assert hasattr(settings, "ollama_model")
        assert settings.ollama_base_url.startswith("http")


# ─── Test 8: Full integration with style patterns ───────────────────────

class TestFullIntegration:
    """Full integration test with style patterns."""

    @pytest.mark.asyncio
    async def test_generate_with_style_patterns(
        self,
        test_session: AsyncSession,
        admin_user_with_holding: User,
        holding_with_patterns: Holding,
    ):
        """Generation should include style patterns from holding."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.is_mock = True
        mock_llm.chat_completion.return_value = json.dumps(
            MOCK_RESPONSE, ensure_ascii=False
        )

        service = GeneratorService(llm_client=mock_llm)

        result = await service.generate(
            context_description="Регламент с паттернами",
            user=admin_user_with_holding,
            holding_id=admin_user_with_holding.active_holding_id,
            db=test_session,
        )

        assert result is not None
        assert result.status == "draft"

        # Verify the LLM was called with a prompt containing style patterns
        call_args = mock_llm.chat_completion.call_args
        assert call_args is not None
        messages = call_args[0][0]  # first positional arg
        system_content = messages[0]["content"]
        assert "СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА" in system_content
        # Should contain at least one of the typical phrases from the fixture
        assert (
            "Настоящий документ устанавливает" in system_content
            or "Типичные фразы" in system_content
        )

    @pytest.mark.asyncio
    async def test_prompt_builder_compatibility(
        self, holding_with_patterns: Holding
    ):
        """Old-style call without style_patterns should still work."""
        # This is the old call pattern (without style_patterns)
        messages = prompt_builder.build_messages(
            holding=holding_with_patterns,
            context_description="Старый вызов",
            drafts_content=None,
            terms=[],
            influencing_docs=[],
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        # Style patterns section should be present (auto-extracted from holding)
        system_content = messages[0]["content"]
        assert "СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА" in system_content
        # Even without explicit style_patterns, _build_system_prompt should
        # auto-extract them from holding
        assert "СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА" in system_content
