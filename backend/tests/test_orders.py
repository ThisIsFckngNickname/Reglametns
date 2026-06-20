"""
Tests for order endpoints.
"""

import pytest
from httpx import AsyncClient

from app.models.user import User

TEST_DATA_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "test_data")


def _get_sample_path(filename: str) -> str:
    path = __import__("os").path.join(TEST_DATA_DIR, filename)
    assert __import__("os").path.exists(path), f"Test file not found: {path}"
    return path


class TestOrders:
    """Tests for order CRUD."""

    @pytest.mark.asyncio
    async def test_upload_order(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload an order successfully."""
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            response = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={
                    "title": "Test Order",
                    "order_number": "123",
                    "order_date": "2026-06-20",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["title"] == "Test Order"
        assert data["order_number"] == "123"
        assert data["status"] == "active"
        assert data["file_type"] == "docx"

    @pytest.mark.asyncio
    async def test_upload_order_with_parse(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload an order and let the parser extract number/date."""
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            response = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={
                    "title": "Parsed Order",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["title"] == "Parsed Order"
        # The sample.docx doesn't have order patterns, so number/date may be None
        # But the upload should still succeed

    @pytest.mark.asyncio
    async def test_list_orders(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """List orders with pagination."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Order 1"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["title"] is not None

    @pytest.mark.asyncio
    async def test_get_order(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Get order details."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Detail Order", "order_number": "456"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id
        assert data["title"] == "Detail Order"
        assert data["order_number"] == "456"

    @pytest.mark.asyncio
    async def test_update_order(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Update order metadata."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Update Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = upload_resp.json()["id"]

        response = await client.put(
            f"/api/v1/orders/{order_id}",
            json={"title": "Updated Title", "order_number": "789"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["order_number"] == "789"

    @pytest.mark.asyncio
    async def test_cancel_order(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Cancel an order."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Cancel Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = upload_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify status changed
        get_resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_link_order_to_document(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Link an order to a document."""
        docx_path = _get_sample_path("sample.docx")

        # Upload a document
        with open(docx_path, "rb") as f:
            doc_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Order Link Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = doc_resp.json()["id"]

        # Upload an order
        with open(docx_path, "rb") as f:
            order_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Linked Order"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = order_resp.json()["id"]

        # Link order to document
        response = await client.post(
            f"/api/v1/orders/{order_id}/documents",
            json={"document_id": doc_id, "link_type": "amends"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["document_id"] == doc_id
        assert data["link_type"] == "amends"
        assert data["document_title"] == "Order Link Doc"

    @pytest.mark.asyncio
    async def test_unlink_order_from_document(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Remove an order-document link."""
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            doc_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Unlink Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = doc_resp.json()["id"]

        with open(docx_path, "rb") as f:
            order_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Unlink Order"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = order_resp.json()["id"]

        # Create link
        link_resp = await client.post(
            f"/api/v1/orders/{order_id}/documents",
            json={"document_id": doc_id, "link_type": "relates_to"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        link_id = link_resp.json()["id"]

        # Delete link
        response = await client.delete(
            f"/api/v1/orders/{order_id}/documents/{link_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_get_order_documents(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Get documents linked to an order."""
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            doc_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Linked Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = doc_resp.json()["id"]

        with open(docx_path, "rb") as f:
            order_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Get Docs Order"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        order_id = order_resp.json()["id"]

        # Link
        await client.post(
            f"/api/v1/orders/{order_id}/documents",
            json={"document_id": doc_id, "link_type": "supersedes"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Get linked documents
        response = await client.get(
            f"/api/v1/orders/{order_id}/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["document_id"] == doc_id
        assert data[0]["document_title"] == "Linked Doc"
