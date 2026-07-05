"""
ProviderSelector — автоматический выбор провайдера (auto mode).

Логика:
1. Если topic содержит юр. маркеры → YandexGPT (приоритет)
2. Если topic > 50 слов → YandexGPT (приоритет)
3. Иначе → Ollama > Groq > YandexGPT (цепочка)
4. Fallback: при ошибке генерации → переключение на следующего
5. При ручном выборе — без fallback
"""

import logging
import time
from typing import Optional, List
from app.providers.base import BaseLLMProvider, ProviderError

logger = logging.getLogger(__name__)

LEGAL_MARKERS = [
    "ПДн", "152-ФЗ", "коммерческая тайна", "персональные данные",
    "персональных данных", "GDPR", "confidentiality", "trade secret",
    "персональным данным", "Защита персональных", "О персональных",
    "ФЗ-152", "152-ФЗ", "ПДн",
    "конфиденциальность", "секретность", "гостайна",
]

DEFAULT_CHAIN = ["ollama", "groq", "yandexgpt"]


class HealthResult:
    def __init__(self, available: bool, checked_at: float):
        self.available = available
        self.checked_at = checked_at


class ProviderSelector:
    """Выбор провайдера с умными правилами."""

    def __init__(self, providers: list[BaseLLMProvider]):
        self._providers = {}
        for p in providers:
            pid = p.name.lower().split()[0]
            self._providers[pid] = p
        self._health_cache: dict[str, HealthResult] = {}
        self._cache_ttl = 30

    def _get_provider_id(self, provider: BaseLLMProvider) -> str:
        return provider.name.lower().split()[0]

    def _check_legal_markers(self, topic: str) -> bool:
        topic_lower = topic.lower()
        return any(marker.lower() in topic_lower for marker in LEGAL_MARKERS)

    def _count_words(self, topic: str) -> int:
        return len(topic.split())

    async def refresh_health(self) -> None:
        now = time.time()
        for pid, provider in self._providers.items():
            try:
                available = await provider.health_check()
            except Exception:
                available = False
            self._health_cache[pid] = HealthResult(available, now)

    async def _get_health(self, provider_id: str) -> bool:
        now = time.time()
        cached = self._health_cache.get(provider_id)
        if cached and (now - cached.checked_at) < self._cache_ttl:
            return cached.available

        provider = self._providers.get(provider_id)
        if not provider:
            return False

        try:
            available = await provider.health_check()
        except Exception:
            available = False

        self._health_cache[provider_id] = HealthResult(available, now)
        return available

    def _get_priority_chain(self, topic: str) -> list[str]:
        if self._check_legal_markers(topic):
            logger.info("Auto-select: legal markers → YandexGPT priority")
            return ["yandexgpt", "ollama", "groq"]
        if self._count_words(topic) > 50:
            logger.info("Auto-select: long topic → YandexGPT priority")
            return ["yandexgpt", "ollama", "groq"]
        logger.info("Auto-select: default chain → Ollama > Groq > YandexGPT")
        return DEFAULT_CHAIN

    async def select(
        self,
        topic: str,
        preference: str = "auto",
    ) -> BaseLLMProvider:
        """Выбрать провайдера.

        Args:
            topic: Тема регламента.
            preference: "auto", "groq", "yandexgpt", "ollama"

        Returns:
            Выбранный провайдер.

        Raises:
            ValueError: Если ни один провайдер не доступен.
        """
        if preference != "auto":
            provider = self._providers.get(preference)
            if not provider:
                raise ValueError(f"Unknown provider: {preference}")
            healthy = await self._get_health(preference)
            if not healthy:
                raise ValueError(
                    f"Provider '{provider.name}' is not available. "
                    f"Check configuration or try another provider."
                )
            return provider

        chain = self._get_priority_chain(topic)
        for pid in chain:
            healthy = await self._get_health(pid)
            if healthy:
                provider = self._providers.get(pid)
                if provider:
                    logger.info("Auto-select: chosen %s", provider.name)
                    return provider

        raise ValueError(
            "No AI providers available. "
            "Please check that at least one provider is configured and running."
        )

    def list_providers_with_status(self) -> list[dict]:
        result = []
        for pid, provider in self._providers.items():
            cached = self._health_cache.get(pid)
            result.append({
                "id": pid,
                "name": provider.name,
                "available": cached.available if cached else False,
                "model": provider.model,
                "error": None if (cached and cached.available) else
                         "Health-check pending" if not cached else
                         "Provider is not available",
            })
        return result
