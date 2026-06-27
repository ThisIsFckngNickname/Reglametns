"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """Interface for file storage backends."""

    @abstractmethod
    async def save(self, key: str, content: bytes) -> str:
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...
