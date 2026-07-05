"""
Абстрактный базовый класс BaseLLMProvider и кастомные исключения.
"""

from abc import ABC, abstractmethod
from typing import Optional


# ───────────────────────────── Exceptions ─────────────────────────────


class ProviderError(Exception):
    """Базовое исключение для ошибок провайдера."""

    def __init__(self, message: str, provider_name: str = "unknown"):
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] {message}")


class ProviderTimeoutError(ProviderError):
    """Таймаут запроса к провайдеру."""

    def __init__(self, provider_name: str = "unknown", timeout: int = 60):
        super().__init__(
            f"Timeout after {timeout}s",
            provider_name=provider_name,
        )


class ProviderAuthError(ProviderError):
    """Ошибка аутентификации (неверный API-ключ, folder_id и т.д.)."""

    def __init__(self, provider_name: str = "unknown", detail: str = ""):
        msg = f"Authentication failed: {detail}" if detail else "Authentication failed"
        super().__init__(msg, provider_name=provider_name)


class ProviderRateLimitError(ProviderError):
    """Превышен лимит запросов (HTTP 429)."""

    def __init__(self, provider_name: str = "unknown", retry_after: Optional[int] = None):
        msg = f"Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(msg, provider_name=provider_name)


class ProviderUnavailableError(ProviderError):
    """Сервис провайдера недоступен (HTTP 5xx)."""

    def __init__(self, provider_name: str = "unknown", status_code: int = 503, detail: str = ""):
        msg = f"Service unavailable (HTTP {status_code})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg, provider_name=provider_name)


# ───────────────────────────── Base Class ─────────────────────────────


class BaseLLMProvider(ABC):
    """Абстрактный базовый класс для всех LLM-провайдеров."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Человекочитаемое имя провайдера (например, 'Groq Cloud')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Идентификатор модели (например, 'llama-3.3-70b-versatile')."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 32768,
    ) -> str:
        """
        Отправить запрос к LLM и получить ответ.

        Args:
            prompt: Пользовательский промпт (тема регламента).
            system_prompt: Системный промпт (инструкция для LLM).
            temperature: Температура генерации (по умолч. 0.7).
            max_tokens: Максимум токенов в ответе.

        Returns:
            Сырой текст ответа от LLM.

        Raises:
            ProviderTimeoutError: Таймаут запроса (>timeout сек).
            ProviderAuthError: Ошибка аутентификации.
            ProviderRateLimitError: Превышен лимит запросов.
            ProviderUnavailableError: Сервис недоступен (5xx).
            ProviderError: Любая другая ошибка провайдера.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить доступность провайдера.

        Для Groq — лёгкий запрос к GET /models с API-ключом.

        Returns:
            True если провайдер доступен, иначе False.
        """
        ...
