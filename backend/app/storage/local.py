"""Local filesystem storage backend."""

import os

from app.storage.base import BaseStorage


class LocalStorage(BaseStorage):
    """Store files on the local filesystem."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve(self, key: str) -> str:
        path = os.path.normpath(os.path.join(self.base_dir, key))
        if not path.startswith(self.base_dir):
            raise PermissionError(f"Path traversal detected: {key}")
        return path

    async def save(self, key: str, content: bytes) -> str:
        path = self._resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return key

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {key}")
        with open(path, "rb") as f:
            return f.read()

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return os.path.exists(path)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if os.path.exists(path):
            os.remove(path)

    def get_full_path(self, key: str) -> str:
        return self._resolve(key)
