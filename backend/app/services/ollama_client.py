"""
Ollama LLM client for self-hosted local models.
API: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """Client for Ollama self-hosted LLM."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self._mock_mode = False

    @property
    def is_mock(self) -> bool:
        return self._mock_mode

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 48000,
    ) -> str:
        """Send chat completion to Ollama."""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

            content = result.get("message", {}).get("content", "")
            if not content:
                logger.warning("Ollama returned empty content")
                return ""

            return content

        except httpx.ConnectError as e:
            logger.error(f"Ollama connection failed: {e}. Is Ollama running?")
            self._mock_mode = True
            raise RuntimeError(
                f"Ollama is not available at {self.base_url}. "
                f"Start Ollama and make sure model '{self.model}' is pulled."
            ) from e
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            self._mock_mode = True
            raise


# Singleton
ollama_client = OllamaClient()
