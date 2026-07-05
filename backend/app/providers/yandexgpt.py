"""
YandexGPTProvider — реализация BaseLLMProvider через YandexGPT API.
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

YANDEXGPT_API_BASE = "https://llm.api.cloud.yandex.net"


class YandexGPTProvider(BaseLLMProvider):
    """Провайдер для YandexGPT."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        folder_id: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self._api_key = api_key or settings.yandexgpt_api_key
        self._folder_id = folder_id or settings.yandexgpt_folder_id
        self._model = model or "yandexgpt/5-pro"
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "YandexGPT"

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
        if not self._api_key or not self._folder_id:
            raise ProviderAuthError(
                provider_name=self.name,
                detail="YandexGPT API key or folder ID not configured",
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})
        messages.append({"role": "user", "text": prompt})

        payload = {
            "modelUri": f"gpt://{self._folder_id}/{self._model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": messages,
        }

        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info("Sending request to YandexGPT (model=%s)", self._model)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{YANDEXGPT_API_BASE}/foundationModels/v1/completion",
                    json=payload,
                    headers=headers,
                )
            except httpx.TimeoutException:
                raise ProviderTimeoutError(provider_name=self.name, timeout=self._timeout)
            except httpx.ConnectError as e:
                raise ProviderUnavailableError(provider_name=self.name, detail=str(e))
            except httpx.HTTPError as e:
                raise ProviderError(f"HTTP error: {e}", provider_name=self.name)

        if response.status_code == 401:
            raise ProviderAuthError(provider_name=self.name, detail="Invalid API key")
        elif response.status_code == 429:
            raise ProviderRateLimitError(provider_name=self.name)
        elif response.status_code >= 500:
            raise ProviderUnavailableError(
                provider_name=self.name, status_code=response.status_code
            )
        elif response.status_code != 200:
            raise ProviderError(
                f"Unexpected status {response.status_code}: {response.text[:500]}",
                provider_name=self.name,
            )

        try:
            data = response.json()
            result = data["result"]["alternatives"][0]["message"]["text"]
            return result.strip()
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(
                f"Failed to parse YandexGPT response: {e}",
                provider_name=self.name,
            )

    async def health_check(self) -> bool:
        if not self._api_key or not self._folder_id:
            logger.warning("YandexGPT health-check skipped: not configured")
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{YANDEXGPT_API_BASE}/foundationModels/v1/completion",
                    json={
                        "modelUri": f"gpt://{self._folder_id}/{self._model}",
                        "completionOptions": {"stream": False, "maxTokens": 1},
                        "messages": [{"role": "user", "text": "."}],
                    },
                    headers={
                        "Authorization": f"Api-Key {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning("YandexGPT health-check failed: %s", e)
            return False
