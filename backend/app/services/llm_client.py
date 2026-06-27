"""Abstract LLM client interface."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Returns True if running in mock mode."""
        ...

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 32000,
    ) -> str:
        """Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Generation temperature (0.0-1.0).
            max_tokens: Maximum tokens in response.

        Returns:
            Response text from the model.
        """
        ...
