"""
Tests for the storage abstraction layer.

- LocalStorage is always tested.
- S3Storage tests run only if S3_ENDPOINT_URL env var is set.
"""

import os
import tempfile

import pytest

from app.storage.base import BaseStorage
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


# ─── Local Storage Tests ────────────────────────────────────────────────


class TestLocalStorage:
    """Test LocalStorage on a temporary directory."""

    @pytest.fixture
    def storage(self):
        """Create a LocalStorage with a temp base dir."""
        tmp_dir = tempfile.mkdtemp()
        return LocalStorage(base_dir=tmp_dir)

    @pytest.mark.asyncio
    async def test_save_and_read(self, storage: LocalStorage):
        """Save bytes and read them back."""
        key = await storage.save("hello.txt", b"Hello, World!")
        assert key == "hello.txt"
        content = await storage.read("hello.txt")
        assert content == b"Hello, World!"

    @pytest.mark.asyncio
    async def test_exists(self, storage: LocalStorage):
        """exists() returns True for saved file, False otherwise."""
        assert not await storage.exists("missing.txt")
        await storage.save("present.txt", b"data")
        assert await storage.exists("present.txt")

    @pytest.mark.asyncio
    async def test_delete(self, storage: LocalStorage):
        """After delete, the file no longer exists."""
        await storage.save("todelete.txt", b"delete me")
        assert await storage.exists("todelete.txt")
        await storage.delete("todelete.txt")
        assert not await storage.exists("todelete.txt")

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, storage: LocalStorage):
        """Reading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage.read("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, storage: LocalStorage):
        """Saving outside base_dir should raise PermissionError."""
        with pytest.raises(PermissionError):
            await storage.save("../../evil.txt", b"bad")

    @pytest.mark.asyncio
    async def test_save_in_subdirectory(self, storage: LocalStorage):
        """Saving in a subdirectory creates intermediate dirs."""
        key = await storage.save("sub/dir/file.txt", b"nested")
        assert key == "sub/dir/file.txt"
        assert await storage.exists("sub/dir/file.txt")
        content = await storage.read("sub/dir/file.txt")
        assert content == b"nested"

    @pytest.mark.asyncio
    async def test_get_full_path(self, storage: LocalStorage):
        """get_full_path returns the absolute path."""
        await storage.save("file.txt", b"data")
        full = storage.get_full_path("file.txt")
        assert os.path.isabs(full)
        assert full.endswith("file.txt")
        assert os.path.exists(full)

    @pytest.mark.asyncio
    async def test_roundtrip_binary(self, storage: LocalStorage):
        """Binary content (e.g. docx/pdf) is preserved exactly."""
        binary = bytes(range(256))
        await storage.save("binary.bin", binary)
        read_back = await storage.read("binary.bin")
        assert read_back == binary


# ─── S3 Storage Tests ───────────────────────────────────────────────────

S3_ENABLED = os.environ.get("S3_ENDPOINT_URL") is not None


@pytest.mark.skipif(
    not S3_ENABLED,
    reason="S3 tests require S3_ENDPOINT_URL env var (e.g. http://localhost:9000)",
)
class TestS3Storage:
    """Test S3Storage against a real S3-compatible endpoint (MinIO).

    Configure via environment variables:
        S3_ENDPOINT_URL  (required)
        S3_ACCESS_KEY    (default: minioadmin)
        S3_SECRET_KEY    (default: minioadmin)
        S3_BUCKET        (default: srp-test)
    """

    @pytest.fixture
    def storage(self):
        """Create an S3Storage pointing to the configured endpoint."""
        return S3Storage(
            bucket=os.environ.get("S3_BUCKET", "srp-test"),
            endpoint_url=os.environ["S3_ENDPOINT_URL"],
            access_key=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
        )

    @pytest.mark.asyncio
    async def test_save_and_read(self, storage: S3Storage):
        """Save bytes to S3 and read them back."""
        key = await storage.save("s3_hello.txt", b"Hello from S3!")
        assert key == "s3_hello.txt"
        content = await storage.read("s3_hello.txt")
        assert content == b"Hello from S3!"
        # Cleanup
        await storage.delete("s3_hello.txt")

    @pytest.mark.asyncio
    async def test_exists(self, storage: S3Storage):
        """exists() returns True for saved file, False otherwise."""
        assert not await storage.exists("s3_missing.txt")
        await storage.save("s3_present.txt", b"data")
        assert await storage.exists("s3_present.txt")
        await storage.delete("s3_present.txt")

    @pytest.mark.asyncio
    async def test_delete(self, storage: S3Storage):
        """After delete, the file no longer exists in S3."""
        await storage.save("s3_todelete.txt", b"delete me")
        assert await storage.exists("s3_todelete.txt")
        await storage.delete("s3_todelete.txt")
        assert not await storage.exists("s3_todelete.txt")

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, storage: S3Storage):
        """Reading a non-existent key should raise an exception."""
        with pytest.raises(Exception):
            await storage.read("s3_nonexistent.txt")

    @pytest.mark.asyncio
    async def test_save_in_subdirectory(self, storage: S3Storage):
        """Saving with a path containing slashes works."""
        key = await storage.save("s3_sub/dir/file.txt", b"nested")
        assert key == "s3_sub/dir/file.txt"
        assert await storage.exists("s3_sub/dir/file.txt")
        content = await storage.read("s3_sub/dir/file.txt")
        assert content == b"nested"
        await storage.delete("s3_sub/dir/file.txt")


# ─── Factory Tests ──────────────────────────────────────────────────────


class TestGetStorage:
    """Test the storage factory."""

    def test_local_storage_by_default(self):
        """With default settings, get_storage() returns LocalStorage."""
        from app.storage import get_storage, reset_storage

        reset_storage()
        storage = get_storage()
        assert isinstance(storage, LocalStorage)
        reset_storage()

    @pytest.mark.skipif(
        not S3_ENABLED,
        reason="S3 tests require S3_ENDPOINT_URL",
    )
    def test_s3_storage_with_env(self, monkeypatch):
        """With storage_type=s3 and proper env, get_storage() returns S3Storage."""
        from app.storage import get_storage, reset_storage

        monkeypatch.setenv("STORAGE_TYPE", "s3")
        # Reload config
        import importlib
        from app import config

        importlib.reload(config)

        reset_storage()
        storage = get_storage()
        assert isinstance(storage, S3Storage)
        reset_storage()
