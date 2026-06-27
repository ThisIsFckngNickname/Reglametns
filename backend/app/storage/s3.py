"""S3-compatible storage backend."""

import os
from io import BytesIO

from app.storage.base import BaseStorage


class S3Storage(BaseStorage):
    """Store files in an S3-compatible bucket."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import aiobotocore.session
            session = aiobotocore.session.get_session()
            self._client = await session._create_client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ).__aenter__()
        return self._client

    async def save(self, key: str, content: bytes) -> str:
        client = await self._get_client()
        await client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key

    async def read(self, key: str) -> bytes:
        client = await self._get_client()
        resp = await client.get_object(Bucket=self.bucket, Key=key)
        body = await resp["Body"].read()
        return body

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        try:
            await client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete_object(Bucket=self.bucket, Key=key)
