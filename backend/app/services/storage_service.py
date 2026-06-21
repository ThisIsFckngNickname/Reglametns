"""
Storage service — high-level file storage operations.

Maintains backward compatibility with the existing API while
delegating low-level I/O to the configured storage backend
(local or S3-compatible).
"""

import os
import tempfile
from datetime import datetime, timezone

from fastapi import UploadFile

from app.config import settings
from app.storage import get_storage


class LocalFileStorage:
    """File storage service for uploaded documents and orders.

    This is a high-level facade that:
    - Constructs file paths from business identifiers
    - Delegates actual read/write to the configured storage backend
    - Provides get_full_path() for parsers that need local paths
    """

    BASE_PATH = settings.storage_path

    async def save(
        self, file: UploadFile, company_id: int, document_id: int, version_number: int
    ) -> str:
        """Save file, return relative path.

        Path: {company_id}/{document_id}/{version_number}_{timestamp}.{ext}

        The path is stored in the database and used to retrieve the file later.
        """
        ext = self._get_extension(file.filename or "document")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        filename = f"{version_number}_{timestamp}{ext}"

        relative_dir = os.path.join(str(company_id), str(document_id))
        relative_path = os.path.join(relative_dir, filename)
        relative_path = relative_path.replace("\\", "/")

        content = await file.read()
        await get_storage().save(relative_path, content)

        return relative_path

    async def get(self, file_path: str) -> bytes:
        """Read file from storage."""
        storage = get_storage()
        if not await storage.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        return await storage.read(file_path)

    async def delete(self, file_path: str) -> None:
        """Delete file from storage."""
        await get_storage().delete(file_path)

    async def get_full_path(self, file_path: str) -> str:
        """Return an absolute local filesystem path for the given file.

        For local storage, this returns the real path directly.
        For S3 storage, the file is downloaded to a temporary location.

        NOTE: When using S3, the returned path points to a temporary file
        that may be cleaned up. Do not rely on it persisting.
        """
        from app.storage.local import LocalStorage

        _storage = get_storage()
        if isinstance(_storage, LocalStorage):
            return _storage.get_full_path(file_path)

        # S3 fallback: download to a temporary file
        content = await _storage.read(file_path)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_path)[1])
        tmp.write(content)
        tmp.close()
        return tmp.name

    def _get_extension(self, filename: str) -> str:
        _, ext = os.path.splitext(filename)
        return ext.lower()


# Singleton instance (kept for backward compatibility)
storage = LocalFileStorage()
