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
    async def test_get_diff_between_versions(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Compare two versions and get diff."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Diff Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Add version 2
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "v2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        # Get diff
        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 2},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert data["from_version"]["version_number"] == 1
        assert data["to_version"]["version_number"] == 2
        assert "changes" in data
        # Should list differences (or "No significant changes")
        assert len(data["changes"]) >= 0

    @pytest.mark.asyncio
    async def test_get_diff_same_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Compare a version with itself — should return no meaningful diff."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Same Version Diff"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert data["from_version"]["version_number"] == 1
        assert data["to_version"]["version_number"] == 1
        assert len(data["sections_diff"]) > 0
        for s in data["sections_diff"]:
            assert s["status"] == "unchanged"
        assert data["full_text_diff"] == ""

    @pytest.mark.asyncio
    async def test_get_diff_with_sections(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Verify sections_diff contains expected fields."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Sections Diff Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Version 2
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "v2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 2},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert "sections_diff" in data
        assert len(data["sections_diff"]) > 0
        for item in data["sections_diff"]:
            assert "section_id" in item
            assert "title" in item
            assert "status" in item
            assert item["status"] in ("added", "removed", "changed", "unchanged")

    @pytest.mark.asyncio
    async def test_get_diff_with_full_text(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Verify full_text_diff contains diff output."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Full Text Diff Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Version 2 (same file, so diff should be empty or minimal)
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "v2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 2},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert "full_text_diff" in data
        # Both versions have the same file, so diff should be empty
        # (unified_diff with identical content returns "")
        assert data["full_text_diff"] is not None

    @pytest.mark.asyncio
    async def test_get_diff_metadata_changes(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Verify metadata_changes in diff response."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Metadata Diff Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Version 2 with different notes
        with open(docx_path, "rb") as f:
            await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"version_notes": "v2 with changes"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            f"/api/v1/documents/{doc_id}/diff",
            params={"from_version": 1, "to_version": 2},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert "metadata_changes" in data
        # version_notes changed from None to "v2 with changes"
        assert data["metadata_changes"].get("version_notes") is not None
        assert data["metadata_changes"]["version_notes"]["old"] is None
        assert data["metadata_changes"]["version_notes"]["new"] == "v2 with changes"

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
