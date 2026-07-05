"""
OllamaProvider — реализация BaseLLMProvider через локальный Ollama API.
"""

import logging
from typing import Optional
import httpx
from app.config import settings
from app.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер для локальной Ollama."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 0,
    ):
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._timeout = timeout if timeout > 0 else settings.provider_timeout

    @property
    def name(self) -> str:
        return "Ollama (локальный)"

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
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt or "",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        logger.info(
            "Sending request to Ollama (model=%s, temperature=%s, max_tokens=%s)",
            self._model, temperature, max_tokens,
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                )
            except httpx.ConnectError as e:
                raise ProviderUnavailableError(
                    provider_name=self.name,
                    detail=f"Cannot connect to Ollama at {self._base_url}: {e}",
                )
            except httpx.TimeoutException:
                raise ProviderTimeoutError(
                    provider_name=self.name,
                    timeout=self._timeout,
                )
            except httpx.HTTPError as e:
                raise ProviderError(f"HTTP error: {e}", provider_name=self.name)

        if response.status_code != 200:
            raise ProviderError(
                f"Ollama returned status {response.status_code}: {response.text[:500]}",
                provider_name=self.name,
            )

        try:
            data = response.json()
            return data.get("response", "").strip()
        except (ValueError, KeyError) as e:
            raise ProviderError(
                f"Failed to parse Ollama response: {e}",
                provider_name=self.name,
            )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                model_name = self._model
                return any(model_name in m for m in models)
        except Exception as e:
            logger.warning("Ollama health-check failed: %s", e)
            return False
