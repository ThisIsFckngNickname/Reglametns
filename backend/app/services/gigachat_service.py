"""
GigaChat Pro API client.

Docs: https://developers.sber.ru/docs/ru/gigachat/api/overview

Supports:
  - OAuth 2.0 client credentials flow
  - Chat completion with GigaChat-Pro model
  - Retry logic with exponential backoff
  - Token caching (30 min lifetime)
  - Mock mode when credentials are not configured
"""

import json
import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MOCK_RESPONSE = {
    "title": "Регламент «Название документа»",
    "description": "Настоящий документ определяет порядок и правила...",
    "sections": [
        {
            "title": "1. Общие положения",
            "level": 1,
            "content": (
                "1.1. Настоящий регламент (далее — Регламент) разработан в соответствии "
                "с действующим законодательством Российской Федерации и Уставом организации.\n"
                "1.2. Регламент определяет цели, задачи, порядок и правила реализации "
                "процессов, указанных в контекстном описании.\n"
                "1.3. Требования настоящего Регламента обязательны для исполнения "
                "всеми сотрудниками и подразделениями организации."
            ),
            "subsections": [
                {
                    "title": "1.1. Цели и задачи",
                    "level": 2,
                    "content": (
                        "Основной целью настоящего Регламента является обеспечение "
                        "единообразного подхода к выполнению процессов.\n"
                        "Задачами Регламента являются:\n"
                        "- установление единых требований и правил;\n"
                        "- определение ответственности участников процессов;\n"
                        "- обеспечение контроля и мониторинга выполнения."
                    ),
                },
                {
                    "title": "1.2. Область применения",
                    "level": 2,
                    "content": (
                        "Действие настоящего Регламента распространяется на все "
                        "структурные подразделения организации."
                    ),
                },
            ],
        },
        {
            "title": "2. Термины и определения",
            "level": 1,
            "content": (
                "В настоящем Регламенте используются следующие термины и определения."
            ),
            "subsections": [],
        },
        {
            "title": "3. Порядок выполнения процессов",
            "level": 1,
            "content": (
                "3.1. Процессы выполняются в соответствии с утверждённым порядком.\n"
                "3.2. Ответственные лица назначаются приказом руководителя."
            ),
            "subsections": [
                {
                    "title": "3.1. Этап 1: Инициация",
                    "level": 2,
                    "content": "Этап инициации включает подготовку и согласование необходимых документов.",
                },
                {
                    "title": "3.2. Этап 2: Выполнение",
                    "level": 2,
                    "content": "Этап выполнения включает реализацию процессов в соответствии с утверждённым порядком.",
                },
            ],
        },
        {
            "title": "4. Заключительные положения",
            "level": 1,
            "content": (
                "4.1. Настоящий Регламент вступает в силу с даты его утверждения.\n"
                "4.2. Контроль за исполнением Регламента возлагается на руководителя."
            ),
            "subsections": [],
        },
    ],
    "terms": [
        {"term": "Регламент", "definition": "Нормативный документ, устанавливающий порядок выполнения процессов"},
        {"term": "Процесс", "definition": "Совокупность последовательных действий, направленных на достижение результата"},
    ],
    "abbreviations": [
        {"abbreviation": "ООО", "full_form": "Общество с ограниченной ответственностью"},
        {"abbreviation": "РФ", "full_form": "Российская Федерация"},
    ],
    "references": [
        {"title": "Конституция Российской Федерации", "source": "Принята всенародным голосованием 12.12.1993"},
        {"title": "Гражданский кодекс Российской Федерации", "source": "Федеральный закон № 51-ФЗ от 30.11.1994"},
    ],
}


class GigaChatClient:
    """Client for GigaChat Pro API."""

    def __init__(self):
        self.auth_url = settings.gigachat_auth_url
        self.api_url = settings.gigachat_api_url
        self.client_id = settings.gigachat_client_id
        self.client_secret = settings.gigachat_client_secret
        self.model = settings.gigachat_model
        self.verify_ssl = settings.gigachat_verify_ssl
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._mock_mode = not (bool(self.client_id) and bool(self.client_secret))

    @property
    def is_mock(self) -> bool:
        """Returns True if running in mock mode (no GigaChat credentials)."""
        return self._mock_mode

    async def _get_access_token(self) -> str:
        """Get OAuth token via client credentials."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        logger.info("Requesting GigaChat access token...")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(time.time()),
        }
        data = {
            "scope": "GIGACHAT_API_PERS",
        }
        auth = (self.client_id, self.client_secret)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            response = await client.post(
                self.auth_url,
                headers=headers,
                data=data,
                auth=auth,
            )
            response.raise_for_status()
            result = response.json()

        self._access_token = result.get("access_token", "")
        expires_in = result.get("expires_in", 1800)  # default 30 min
        self._token_expires_at = time.time() + expires_in - 60  # 1 min safety margin
        logger.info("GigaChat access token obtained successfully")
        return self._access_token

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 8000,
    ) -> str:
        """Send chat completion request to GigaChat Pro.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Generation temperature (0.0-1.0).
            max_tokens: Maximum tokens in response.

        Returns:
            Response text from the model.
        """
        if self._mock_mode:
            logger.info("GigaChat in mock mode — returning predefined response")
            return json.dumps(MOCK_RESPONSE, ensure_ascii=False)

        token = await self._get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        result = await self._request_with_retry(
            "POST",
            self.api_url,
            headers=headers,
            json=payload,
        )
        return self._extract_response_text(result)

    def _extract_response_text(self, response_data: dict) -> str:
        """Extract text from GigaChat response, checking finish_reason."""
        choices = response_data.get("choices", [])
        if not choices:
            logger.warning("GigaChat response has no choices")
            return ""

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        finish_reason = choice.get("finish_reason", "")
        if finish_reason == "length":
            logger.warning(
                "GigaChat response was truncated by max_tokens. "
                "Consider increasing GENERATION_MAX_TOKENS."
            )

        return content

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> dict:
        """HTTP request with retry logic (3 retries, exponential backoff)."""
        max_retries = 3
        timeout_val = kwargs.pop("timeout", settings.generation_timeout)

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    verify=self.verify_ssl,
                    timeout=timeout_val,
                ) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"GigaChat HTTP error (attempt {attempt + 1}/{max_retries}): "
                    f"{e.response.status_code} — {e.response.text}"
                )
                if attempt == max_retries - 1:
                    raise
                await self._exponential_backoff(attempt)
            except httpx.TimeoutException as e:
                logger.error(
                    f"GigaChat timeout (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                await self._exponential_backoff(attempt)
            except httpx.RequestError as e:
                logger.error(
                    f"GigaChat request error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                await self._exponential_backoff(attempt)

        raise RuntimeError("GigaChat request failed after all retries")

    async def _exponential_backoff(self, attempt: int) -> None:
        """Wait with exponential backoff."""
        delay = 2 ** (attempt + 1)
        logger.info(f"Retrying in {delay}s...")
        await self._async_sleep(delay)

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(seconds)


# Singleton
gigachat_client = GigaChatClient()
