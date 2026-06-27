"""Storage backend abstraction — local or S3."""

from app.config import settings

_storage_instance = None


def get_storage():
    """Return a singleton storage backend based on settings."""
    global _storage_instance
    if _storage_instance is None:
        if settings.storage_type == "s3":
            from app.storage.s3 import S3Storage
            _storage_instance = S3Storage(
                bucket=settings.s3_bucket,
                endpoint_url=settings.s3_endpoint_url,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
            )
        else:
            from app.storage.local import LocalStorage
            _storage_instance = LocalStorage(base_dir=settings.storage_path)
    return _storage_instance


def reset_storage():
    """Reset the cached storage instance (used in tests)."""
    global _storage_instance
    _storage_instance = None
