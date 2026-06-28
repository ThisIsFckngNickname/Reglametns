"""Tests for document amendment relationships (B3)."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_link import DocumentLink
from app.models.document_status import DocumentStatus
from app.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def setup_amendment_data(test_session: AsyncSession, admin_user: User):
    """Create two documents linked via 'amends'."""
    order = Document(
        company_id=admin_user.active_company_id,
        title="Приказ №1",
        document_type="order",
        status=DocumentStatus.APPROVED,
        created_by=admin_user.id,
    )
    regulation = Document(
        company_id=admin_user.active_company_id,
        title="Регламент по ГСМ",
        document_type="regulation",
        status=DocumentStatus.APPROVED,
        created_by=admin_user.id,
    )
    test_session.add_all([order, regulation])
    await test_session.flush()

    link = DocumentLink(
        source_document_id=order.id,
        target_document_id=regulation.id,
        link_type="amends",
        is_manual=True,
        created_by=admin_user.id,
    )
    test_session.add(link)
    await test_session.flush()

    return {
        "order_id": order.id,
        "regulation_id": regulation.id,
        "link_id": link.id,
    }


@pytest.mark.asyncio
async def test_get_amendments(
    client: AsyncClient,
    admin_token: str,
    setup_amendment_data: dict,
):
    """Test GET /api/v1/documents/{id}/amendments."""
    reg_id = setup_amendment_data["regulation_id"]
    resp = await client.get(
        f"/api/v1/documents/{reg_id}/amendments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Приказ №1"
    assert data[0]["document_type"] == "order"
    assert data[0]["link_id"] == setup_amendment_data["link_id"]
    assert "created_at" in data[0]


@pytest.mark.asyncio
async def test_get_amended_documents(
    client: AsyncClient,
    admin_token: str,
    setup_amendment_data: dict,
):
    """Test GET /api/v1/documents/{id}/amended-documents."""
    order_id = setup_amendment_data["order_id"]
    resp = await client.get(
        f"/api/v1/documents/{order_id}/amended-documents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Регламент по ГСМ"
    assert data[0]["document_type"] == "regulation"
    assert data[0]["link_id"] == setup_amendment_data["link_id"]


@pytest.mark.asyncio
async def test_amendments_empty_for_unrelated_doc(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    test_session: AsyncSession,
):
    """Test that a document with no amends links returns empty list."""
    doc = Document(
        company_id=admin_user.active_company_id,
        title="Новый документ",
        document_type="policy",
        status=DocumentStatus.DRAFT,
        created_by=admin_user.id,
    )
    test_session.add(doc)
    await test_session.flush()

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/amendments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    assert resp.json() == []


@pytest.mark.asyncio
async def test_amended_docs_empty_for_unrelated_doc(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    test_session: AsyncSession,
):
    """Test that a document with no outgoing amends returns empty list."""
    doc = Document(
        company_id=admin_user.active_company_id,
        title="Приказ без изменений",
        document_type="order",
        status=DocumentStatus.DRAFT,
        created_by=admin_user.id,
    )
    test_session.add(doc)
    await test_session.flush()

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/amended-documents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    assert resp.json() == []


@pytest.mark.asyncio
async def test_amendments_filters_link_type(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    test_session: AsyncSession,
    setup_amendment_data: dict,
):
    """Test that non-amends links are not included in results."""
    reg_id = setup_amendment_data["regulation_id"]

    # Create a 'references' link (should not appear in amendments)
    ref_link = DocumentLink(
        source_document_id=setup_amendment_data["order_id"],
        target_document_id=reg_id,
        link_type="references",
        is_manual=True,
        created_by=admin_user.id,
    )
    test_session.add(ref_link)
    await test_session.flush()

    # Amendments should still show only 1 result (amends, not references)
    resp = await client.get(
        f"/api/v1/documents/{reg_id}/amendments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    data = resp.json()
    assert len(data) == 1
    assert data[0]["link_id"] == setup_amendment_data["link_id"]


@pytest.mark.asyncio
async def test_amendments_returns_200_for_nonexistent_doc(
    client: AsyncClient,
    admin_token: str,
):
    """Test that a non-existent document returns empty list (not 404)."""
    resp = await client.get(
        "/api/v1/documents/99999/amendments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    assert resp.json() == []


@pytest.mark.asyncio
async def test_amended_docs_returns_200_for_nonexistent_doc(
    client: AsyncClient,
    admin_token: str,
):
    """Test that a non-existent order returns empty list (not 404)."""
    resp = await client.get(
        "/api/v1/documents/99999/amended-documents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    assert resp.json() == []
