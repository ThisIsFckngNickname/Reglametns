"""
Tests for holdings CRUD endpoints and user holding selection.
"""

import pytest
from httpx import AsyncClient

from app.models.holding import Holding
from app.models.user import User


class TestListHoldings:
    """Tests for GET /api/v1/holdings."""

    @pytest.mark.asyncio
    async def test_list_holdings_success(self, client: AsyncClient, admin_user: User, admin_token: str):
        """Should return list of holdings."""
        response = await client.get(
            "/api/v1/holdings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Test Holding"

    @pytest.mark.asyncio
    async def test_list_holdings_no_auth(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.get("/api/v1/holdings")
        assert response.status_code == 401


class TestCreateHolding:
    """Tests for POST /api/v1/holdings."""

    @pytest.mark.asyncio
    async def test_create_holding_as_admin(self, client: AsyncClient, admin_token: str):
        """Admin should be able to create a holding."""
        response = await client.post(
            "/api/v1/holdings",
            json={"name": "New Holding", "inn": "7701987654", "legal_form": "АО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Holding"
        assert data["inn"] == "7701987654"
        assert data["legal_form"] == "АО"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_holding_as_non_admin(self, client: AsyncClient, user_token: str):
        """Non-admin should get 403."""
        response = await client.post(
            "/api/v1/holdings",
            json={"name": "Non Admin Holding", "inn": "7701987654", "legal_form": "АО"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_create_holding_duplicate_name(self, client: AsyncClient, admin_token: str):
        """Should return 409 for duplicate name."""
        # Create first
        await client.post(
            "/api/v1/holdings",
            json={"name": "Unique Holding", "inn": "7701123456", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Try duplicate
        response = await client.post(
            "/api/v1/holdings",
            json={"name": "Unique Holding", "inn": "7701123456", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_create_holding_invalid_inn(self, client: AsyncClient, admin_token: str):
        """Should return 422 for invalid INN."""
        response = await client.post(
            "/api/v1/holdings",
            json={"name": "Invalid Inn", "inn": "123", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_holding_no_auth(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.post(
            "/api/v1/holdings",
            json={"name": "No Auth", "inn": "7701123456", "legal_form": "ООО"},
        )
        assert response.status_code == 401


class TestUpdateHolding:
    """Tests for PUT /api/v1/holdings/{id}."""

    @pytest.mark.asyncio
    async def test_update_holding_success(self, client: AsyncClient, admin_token: str, demo_holding: Holding):
        """Should update a holding."""
        response = await client.put(
            f"/api/v1/holdings/{demo_holding.id}",
            json={"name": "Updated Holding"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Holding"

    @pytest.mark.asyncio
    async def test_update_holding_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent holding."""
        response = await client.put(
            "/api/v1/holdings/99999",
            json={"name": "Not Found"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_holding_not_admin(self, client: AsyncClient, user_token: str, demo_holding: Holding):
        """Non-admin should get 403."""
        response = await client.put(
            f"/api/v1/holdings/{demo_holding.id}",
            json={"name": "Hack"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_holding_duplicate_name(self, client: AsyncClient, admin_token: str, test_session):
        """Should allow duplicate name (new behavior — no uniqueness check on update)."""
        # Create two holdings
        h1 = Holding(name="Holding One", inn="7701123456", legal_form="ООО")
        h2 = Holding(name="Holding Two", inn="7701987654", legal_form="АО")
        test_session.add_all([h1, h2])
        await test_session.flush()

        # Rename h2 to h1's name — now allowed (200, not 409)
        response = await client.put(
            f"/api/v1/holdings/{h2.id}",
            json={"name": "Holding One"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


class TestDeleteHolding:
    """Tests for DELETE /api/v1/holdings/{id}."""

    @pytest.mark.asyncio
    async def test_delete_holding_success(self, client: AsyncClient, admin_token: str, test_session):
        """Should delete a holding (returns 200 with message)."""
        holding = Holding(name="To Delete", inn="7701123456", legal_form="ООО")
        test_session.add(holding)
        await test_session.flush()

        response = await client.delete(
            f"/api/v1/holdings/{holding.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_holding_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent holding."""
        response = await client.delete(
            "/api/v1/holdings/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_holding_with_associations(self, client: AsyncClient, admin_token: str, admin_user: User):
        """Should delete holding even with user associations (cascade delete links)."""
        # admin_user is already associated with "Test Holding"
        response = await client.delete(
            "/api/v1/holdings/1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # New behavior: associations are deleted, holding is deleted
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_holding_not_admin(self, client: AsyncClient, user_token: str, demo_holding: Holding):
        """Non-admin should get 403."""
        response = await client.delete(
            f"/api/v1/holdings/{demo_holding.id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403


class TestSetHolding:
    """Tests for PUT /api/v1/user/holding."""

    @pytest.mark.asyncio
    async def test_set_holding_success(self, client: AsyncClient, admin_user: User, admin_token: str, test_session):
        """Should set active holding."""
        # Create a second holding for the admin to switch to
        holding = Holding(name="Secondary Holding", inn="7701987654", legal_form="АО")
        test_session.add(holding)
        await test_session.flush()

        from app.models.user_holding import UserHolding
        uh = UserHolding(user_id=admin_user.id, holding_id=holding.id, role="member")
        test_session.add(uh)
        await test_session.flush()

        response = await client.put(
            "/api/v1/user/holding",
            json={"holding_id": holding.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Active holding set successfully"
        assert data["active_holding"]["id"] == holding.id
        assert data["active_holding"]["name"] == "Secondary Holding"

    @pytest.mark.asyncio
    async def test_set_holding_not_member(self, client: AsyncClient, admin_token: str, demo_holding: Holding):
        """Should return 401 if user is not a member."""
        # admin_user is not a member of demo_holding
        response = await client.put(
            "/api/v1/user/holding",
            json={"holding_id": demo_holding.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Service raises ForbiddenException (403) for non-membership
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_set_holding_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent holding."""
        response = await client.put(
            "/api/v1/user/holding",
            json={"holding_id": 99999},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
