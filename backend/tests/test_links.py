"""
Tests for document link endpoints.
"""

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestDocumentLinks:
    """Tests for document link CRUD."""

    @pytest.mark.asyncio
    async def test_create_manual_link(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Create a manual link between two documents."""
        # Upload two documents first
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp1 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Source Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc1_id = resp1.json()["id"]

        with open(docx_path, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Target Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc2_id = resp2.json()["id"]

        # Create link
        response = await client.post(
            f"/api/v1/documents/{doc1_id}/links",
            json={
                "target_document_id": doc2_id,
                "link_type": "references",
                "description": "Test link",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["target_document_id"] == doc2_id
        assert data["link_type"] == "references"
        assert data["is_manual"] is True
        assert data["target_title"] == "Target Doc"

    @pytest.mark.asyncio
    async def test_list_links(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """List all links for a document."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp1 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Linked Doc 1"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc1_id = resp1.json()["id"]

        with open(docx_path, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Linked Doc 2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc2_id = resp2.json()["id"]

        # Create a link
        await client.post(
            f"/api/v1/documents/{doc1_id}/links",
            json={"target_document_id": doc2_id, "link_type": "amends"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # List links
        response = await client.get(
            f"/api/v1/documents/{doc1_id}/links",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["target_document_id"] == doc2_id

    @pytest.mark.asyncio
    async def test_delete_link(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Delete a document link."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp1 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Link Delete Doc 1"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc1_id = resp1.json()["id"]

        with open(docx_path, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Link Delete Doc 2"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc2_id = resp2.json()["id"]

        # Create link
        link_resp = await client.post(
            f"/api/v1/documents/{doc1_id}/links",
            json={"target_document_id": doc2_id, "link_type": "supersedes"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        link_id = link_resp.json()["id"]

        # Delete link
        response = await client.delete(
            f"/api/v1/documents/{doc1_id}/links/{link_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify link is gone
        list_resp = await client.get(
            f"/api/v1/documents/{doc1_id}/links",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_link_requires_auth(
        self, client: AsyncClient
    ):
        """Creating a link without auth should return 401."""
        response = await client.post(
            "/api/v1/documents/1/links",
            json={"target_document_id": 2, "link_type": "references"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_link_to_nonexistent_document(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Creating a link to a non-existent document should return 404."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Source"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{doc_id}/links",
            json={"target_document_id": 99999, "link_type": "references"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
