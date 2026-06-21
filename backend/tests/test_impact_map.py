"""
Tests for Impact Map API (document relations aggregation).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_link import DocumentLink
from app.models.order import Order
from app.models.order_document_link import OrderDocumentLink
from app.models.user import User
from tests.test_documents import _get_sample_path


class TestImpactMap:
    """Tests for GET /api/v1/documents/{id}/impact."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_items(data: dict) -> int:
        """Count total items across incoming + outgoing."""
        inc = data["incoming"]
        out = data["outgoing"]
        return (
            len(inc["orders"])
            + len(inc["documents"])
            + len(out["orders"])
            + len(out["documents"])
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_impact_map_empty(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Document with no relations should return empty groups."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Impact Empty Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_id

        # All groups should be empty
        assert data["incoming"]["orders"] == []
        assert data["incoming"]["documents"] == []
        assert data["outgoing"]["orders"] == []
        assert data["outgoing"]["documents"] == []
        assert data["total_relations"] == 0

    @pytest.mark.asyncio
    async def test_impact_map_with_document_links(
        self, client: AsyncClient, admin_user: User, admin_token: str, test_session: AsyncSession
    ):
        """Impact map should include document links in correct direction."""
        # Upload two documents
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

        # Create a link: doc1 -> doc2 (references)
        link_resp = await client.post(
            f"/api/v1/documents/{doc1_id}/links",
            json={
                "target_document_id": doc2_id,
                "link_type": "references",
                "description": "Impact test link",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert link_resp.status_code == 201

        # Get impact map for doc1 (source → target = outgoing)
        response = await client.get(
            f"/api/v1/documents/{doc1_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc1_id
        assert data["total_relations"] == 1

        # Should be in outgoing.documents
        assert len(data["outgoing"]["documents"]) == 1
        item = data["outgoing"]["documents"][0]
        assert item["title"] == "Target Doc"
        assert item["type"] == "references"
        assert item["document_id"] == doc2_id

        # Get impact map for doc2 (incoming)
        response2 = await client.get(
            f"/api/v1/documents/{doc2_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total_relations"] == 1
        assert len(data2["incoming"]["documents"]) == 1
        item2 = data2["incoming"]["documents"][0]
        assert item2["title"] == "Source Doc"
        assert item2["type"] == "references"
        assert item2["document_id"] == doc1_id

    @pytest.mark.asyncio
    async def test_impact_map_with_order_links(
        self, client: AsyncClient, admin_user: User, admin_token: str, test_session: AsyncSession
    ):
        """Impact map should include order links in incoming.orders."""
        # Upload a document
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Order Impact Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        # Upload an order
        with open(docx_path, "rb") as f:
            order_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Test Order", "order_number": "123"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert order_resp.status_code == 201, f"Order upload failed: {order_resp.text}"
        order_id = order_resp.json()["id"]

        # Link order to document
        link_resp = await client.post(
            f"/api/v1/orders/{order_id}/documents",
            json={
                "document_id": doc_id,
                "link_type": "amends",
                "description": "Order impact test",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert link_resp.status_code == 201

        # Get impact map
        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_id
        assert data["total_relations"] == 1

        # Should be in incoming.orders
        assert len(data["incoming"]["orders"]) == 1
        item = data["incoming"]["orders"][0]
        assert item["order_id"] == order_id
        assert item["title"] == "Test Order"
        assert item["type"] == "amends"

    @pytest.mark.asyncio
    async def test_impact_map_bidirectional(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Impact map should show links from both directions."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp1 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Bidirectional A"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_a = resp1.json()["id"]

        with open(docx_path, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Bidirectional B"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_b = resp2.json()["id"]

        # A -> B
        await client.post(
            f"/api/v1/documents/{doc_a}/links",
            json={"target_document_id": doc_b, "link_type": "references"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # B -> A
        await client.post(
            f"/api/v1/documents/{doc_b}/links",
            json={"target_document_id": doc_a, "link_type": "related"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Impact for A should see both links:
        #   outgoing: A -> B (references)
        #   incoming: B -> A (related)
        response = await client.get(
            f"/api/v1/documents/{doc_a}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_relations"] == 2

        outgoing = data["outgoing"]["documents"]
        incoming = data["incoming"]["documents"]
        assert len(outgoing) == 1
        assert len(incoming) == 1
        assert outgoing[0]["document_id"] == doc_b  # A -> B
        assert outgoing[0]["type"] == "references"
        # incoming: B -> A, linked document is B (the source that links to A)
        assert incoming[0]["document_id"] == doc_b
        assert incoming[0]["type"] == "related"

    @pytest.mark.asyncio
    async def test_impact_map_requires_auth(self, client: AsyncClient):
        """Impact map without auth should return 401."""
        response = await client.get("/api/v1/documents/1/impact")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_impact_map_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Impact map for non-existent document should return 404."""
        response = await client.get(
            "/api/v1/documents/99999/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_impact_map_graph_format(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Impact map should include graph with nodes and edges."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Graph Test Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        # Upload a second doc to link
        with open(docx_path, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Linked Doc"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc2_id = resp2.json()["id"]

        # Create link
        await client.post(
            f"/api/v1/documents/{doc_id}/links",
            json={"target_document_id": doc2_id, "link_type": "references"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "graph" in data
        assert "nodes" in data["graph"]
        assert "edges" in data["graph"]
        # Should have at least 2 nodes (center doc + linked doc)
        assert len(data["graph"]["nodes"]) >= 2
        # Should have at least 1 edge
        assert len(data["graph"]["edges"]) >= 1

        # Validate node structure
        for node in data["graph"]["nodes"]:
            assert "id" in node
            assert "label" in node  # frontend uses "label"
            assert "type" in node
            assert "status" in node
            assert node["type"] in ("document", "order")

        # Validate edge structure
        for edge in data["graph"]["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge
            assert "label" in edge

    @pytest.mark.asyncio
    async def test_get_impact_map_graph_with_orders(
        self, client: AsyncClient, admin_user: User, admin_token: str, test_session
    ):
        """Impact map graph should include order nodes when orders link to document."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Graph Order Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        # Upload an order
        with open(docx_path, "rb") as f:
            order_resp = await client.post(
                "/api/v1/orders/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Test Order", "order_number": "G-001"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert order_resp.status_code == 201
        order_id = order_resp.json()["id"]

        # Link order to document
        await client.post(
            f"/api/v1/orders/{order_id}/documents",
            json={"document_id": doc_id, "link_type": "amends"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "graph" in data

        # Should have order node
        order_nodes = [n for n in data["graph"]["nodes"] if n["type"] == "order"]
        assert len(order_nodes) == 1
        assert order_nodes[0]["id"] == f"order:{order_id}"

        # Should have edge from order to document
        order_edges = [e for e in data["graph"]["edges"] if e["type"] == "amends"]
        assert len(order_edges) >= 1

    @pytest.mark.asyncio
    async def test_get_impact_map_graph_empty(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Impact map graph with no relations should have at least the center node."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Empty Graph Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "graph" in data
        # Should have exactly 1 node (center document) and no edges
        assert len(data["graph"]["nodes"]) == 1
        assert len(data["graph"]["edges"]) == 0
        assert data["graph"]["nodes"][0]["id"] == f"doc:{doc_id}"

    # ------------------------------------------------------------------
    # Graph endpoint tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_impact_graph_endpoint(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """GET /documents/{id}/impact/graph should return ImpactGraphResponse."""
        from tests.test_documents import _get_sample_path

        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Graph Endpoint Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/impact/graph",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1  # only center node
        assert data["nodes"][0]["id"] == f"doc:{doc_id}"

    @pytest.mark.asyncio
    async def test_impact_graph_endpoint_requires_auth(
        self, client: AsyncClient
    ):
        """Graph endpoint without auth should return 401."""
        response = await client.get("/api/v1/documents/1/impact/graph")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_impact_graph_endpoint_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Graph endpoint for non-existent document should return 404."""
        response = await client.get(
            "/api/v1/documents/99999/impact/graph",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
