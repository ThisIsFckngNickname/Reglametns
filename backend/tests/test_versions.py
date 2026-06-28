"""
Tests for Phase 7 — document versioning.

Covers:
- List versions (existing)
- Create version (existing)
- Download version by number (new)
- Restore version (new)
- Compare versions diff (new)
- Version not found / document not found
"""

import pytest
from httpx import AsyncClient

from app.models.user import User


def _get_sample_path(name: str) -> str:
    """Get path to a sample file in test_data."""
    import os
    return os.path.join(os.path.dirname(__file__), "test_data", name)


class TestListVersions:
    """Tests for GET /documents/{id}/versions."""

    @pytest.mark.asyncio
    async def test_list_versions_with_notes(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Versions should include version_notes and file_hash."""
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

        # Check version 2 has notes
        v2 = next(v for v in data if v["version_number"] == 2)
        assert v2["version_notes"] == "Second version with fixes"
        # Check file_hash is present
        assert v2.get("file_hash") is not None

    @pytest.mark.asyncio
    async def test_list_versions_empty(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Document without versions should return 404 (not found)."""
        response = await client.get(
            "/api/v1/documents/99999/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestCreateVersion:
    """Tests for POST /documents/{id}/versions."""

    @pytest.mark.asyncio
    async def test_create_new_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Create a new version for an existing document."""
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
        assert data.get("file_hash") is not None


class TestDownloadVersion:
    """Tests for GET /documents/{id}/versions/{version_number}/download."""

    @pytest.mark.asyncio
    async def test_download_version_by_number(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Download a specific version by version number."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Download Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Download version 1
        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions/1/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-disposition") is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_download_version_not_found(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Downloading non-existent version returns 404."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Download NotFound Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions/99/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestRestoreVersion:
    """Tests for POST /documents/{id}/versions/{version_number}/restore."""

    @pytest.mark.asyncio
    async def test_restore_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Restore version 1 should create a new version."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Restore Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Upload version 2
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "Version 2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        # Restore version 1
        response = await client.post(
            f"/api/v1/documents/{doc_id}/versions/1/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["version_number"] == 3
        assert data["restored_from"] == 1
        assert "Восстановлено" in (data.get("version_notes") or "")

    @pytest.mark.asyncio
    async def test_restore_nonexistent_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Restoring non-existent version returns 404."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Restore NotFound Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{doc_id}/versions/99/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestCompareVersions:
    """Tests for GET /documents/{id}/versions/{v1}/diff/{v2}."""

    @pytest.mark.asyncio
    async def test_compare_versions_not_found(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Comparing with non-existent version returns 404."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Diff Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions/1/diff/99",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestVersionPermissions:
    """Tests for version endpoints access control."""

    @pytest.mark.asyncio
    async def test_restore_requires_editor(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Restore should require editor role."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Permissions Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Try without auth
        response = await client.post(
            f"/api/v1/documents/{doc_id}/versions/1/restore",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_requires_auth(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Download should require authentication."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Auth Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions/1/download",
        )
        assert response.status_code == 401
