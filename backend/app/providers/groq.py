"""
GroqProvider — реализация BaseLLMProvider через OpenAI-compatible API.

Использует httpx для async HTTP-запросов.
Модель по умолчанию: llama-3.3-70b-versatile (из .env).
"""

import logging
from typing import Optional
import httpx
from app.config import settings
from app.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderTimeoutError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1"


class GroqProvider(BaseLLMProvider):
    """Провайдер для Groq Cloud (через OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self._api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "Groq Cloud"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 32768,
    ) -> str:
        """Отправить запрос к Groq API и получить ответ."""
        if not self._api_key:
            raise ProviderAuthError(
                provider_name=self.name,
                detail="GROQ_API_KEY not configured. Set it in .env file.",
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending request to Groq (model=%s, temperature=%s, max_tokens=%s)",
            self._model,
            temperature,
            max_tokens,
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{GROQ_API_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            except httpx.TimeoutException:
                raise ProviderTimeoutError(
                    provider_name=self.name,
                    timeout=self._timeout,
                )
            except httpx.ConnectError as e:
                raise ProviderUnavailableError(
                    provider_name=self.name,
                    detail=f"Cannot connect to Groq API: {e}",
                )
            except httpx.HTTPError as e:
                raise ProviderError(
                    f"HTTP error: {e}",
                    provider_name=self.name,
                )

        # Обработка HTTP-статусов
        if response.status_code == 401:
            raise ProviderAuthError(
                provider_name=self.name,
                detail="Invalid API key or unauthorized",
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise ProviderRateLimitError(
                provider_name=self.name,
                retry_after=int(retry_after) if retry_after else None,
            )
        elif response.status_code >= 500:
            raise ProviderUnavailableError(
                provider_name=self.name,
                status_code=response.status_code,
                detail=response.text[:500],
            )
        elif response.status_code != 200:
            raise ProviderError(
                f"Unexpected status {response.status_code}: {response.text[:500]}",
                provider_name=self.name,
            )

        # Парсинг ответа
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(
                f"Failed to parse Groq response: {e}",
                provider_name=self.name,
            )

    async def health_check(self) -> bool:
        """Проверить доступность Groq API (GET /models с API-ключом)."""
        if not self._api_key:
            logger.warning("Groq health-check skipped: API key not configured")
            return False

        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{GROQ_API_BASE}/models",
                    headers=headers,
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("Groq health-check failed: %s", e)
            return False
