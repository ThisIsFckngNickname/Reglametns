"""
Tests for document version endpoints (create version, diff).
"""

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestCreateVersion:
    """Tests for POST /documents/{id}/versions."""

    @pytest.mark.asyncio
    async def test_create_new_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Create a new version for an existing document."""
        from tests.test_documents import _get_sample_path

        # Upload initial document
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Version Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Upload new version
        with open(docx_path, "rb") as f:
            response = await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "Updated content"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["version_number"] == 2
        assert data["version_notes"] == "Updated content"

    @pytest.mark.asyncio
    async def test_list_versions_with_notes(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Versions should include version_notes."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Notes Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Add a version with notes
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "Second version with fixes"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        # Get versions
        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Find version 2
        v2 = next(v for v in data if v["version_number"] == 2)
        assert v2["version_notes"] == "Second version with fixes"

    @pytest.mark.asyncio
    async def test_get_diff_missing_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return 404 when version does not exist."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Missing Version Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
