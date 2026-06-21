"""
Tests for companies CRUD endpoints and user company selection.
"""

import pytest
from httpx import AsyncClient

from app.models.company import Company
from app.models.user import User


class TestListCompanies:
    """Tests for GET /api/v1/companies."""

    @pytest.mark.asyncio
    async def test_list_companies_success(self, client: AsyncClient, admin_user: User, admin_token: str):
        """Should return list of companies."""
        response = await client.get(
            "/api/v1/companies",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Test Company"

    @pytest.mark.asyncio
    async def test_list_companies_no_auth(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.get("/api/v1/companies")
        assert response.status_code == 401


class TestCreateCompany:
    """Tests for POST /api/v1/companies."""

    @pytest.mark.asyncio
    async def test_create_company_as_admin(self, client: AsyncClient, admin_token: str):
        """Admin should be able to create a company."""
        response = await client.post(
            "/api/v1/companies",
            json={"name": "New Company", "inn": "7701987654", "legal_form": "АО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Company"
        assert data["inn"] == "7701987654"
        assert data["legal_form"] == "АО"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_company_as_non_admin(self, client: AsyncClient, user_token: str):
        """Non-admin should get 403."""
        response = await client.post(
            "/api/v1/companies",
            json={"name": "Non Admin Company", "inn": "7701987654", "legal_form": "АО"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_create_company_duplicate_name(self, client: AsyncClient, admin_token: str):
        """Should return 409 for duplicate name."""
        # Create first
        await client.post(
            "/api/v1/companies",
            json={"name": "Unique Company", "inn": "7701123456", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Try duplicate
        response = await client.post(
            "/api/v1/companies",
            json={"name": "Unique Company", "inn": "7701123456", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_create_company_invalid_inn(self, client: AsyncClient, admin_token: str):
        """Should return 422 for invalid INN."""
        response = await client.post(
            "/api/v1/companies",
            json={"name": "Invalid Inn", "inn": "123", "legal_form": "ООО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_company_no_auth(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.post(
            "/api/v1/companies",
            json={"name": "No Auth", "inn": "7701123456", "legal_form": "ООО"},
        )
        assert response.status_code == 401


class TestUpdateCompany:
    """Tests for PUT /api/v1/companies/{id}."""

    @pytest.mark.asyncio
    async def test_update_company_success(self, client: AsyncClient, admin_token: str, demo_company: Company):
        """Should update a company."""
        response = await client.put(
            f"/api/v1/companies/{demo_company.id}",
            json={"name": "Updated Company"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Company"

    @pytest.mark.asyncio
    async def test_update_company_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent company."""
        response = await client.put(
            "/api/v1/companies/99999",
            json={"name": "Not Found"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_company_not_admin(self, client: AsyncClient, user_token: str, demo_company: Company):
        """Non-admin should get 403."""
        response = await client.put(
            f"/api/v1/companies/{demo_company.id}",
            json={"name": "Hack"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_company_duplicate_name(self, client: AsyncClient, admin_token: str, test_session):
        """Should allow duplicate name (new behavior — no uniqueness check on update)."""
        # Create two companies
        c1 = Company(name="Company One", inn="7701123456", legal_form="ООО")
        c2 = Company(name="Company Two", inn="7701987654", legal_form="АО")
        test_session.add_all([c1, c2])
        await test_session.flush()

        # Rename c2 to c1's name — now allowed (200, not 409)
        response = await client.put(
            f"/api/v1/companies/{c2.id}",
            json={"name": "Company One"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


class TestDeleteCompany:
    """Tests for DELETE /api/v1/companies/{id}."""

    @pytest.mark.asyncio
    async def test_delete_company_success(self, client: AsyncClient, admin_token: str, test_session):
        """Should delete a company (returns 200 with message)."""
        company = Company(name="To Delete", inn="7701123456", legal_form="ООО")
        test_session.add(company)
        await test_session.flush()

        response = await client.delete(
            f"/api/v1/companies/{company.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_company_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent company."""
        response = await client.delete(
            "/api/v1/companies/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_company_with_associations(self, client: AsyncClient, admin_token: str, admin_user: User):
        """Should delete company even with user associations (cascade delete links)."""
        # admin_user is already associated with "Test Company"
        response = await client.delete(
            "/api/v1/companies/1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # New behavior: associations are deleted, company is deleted
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_company_not_admin(self, client: AsyncClient, user_token: str, demo_company: Company):
        """Non-admin should get 403."""
        response = await client.delete(
            f"/api/v1/companies/{demo_company.id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403


class TestSetCompany:
    """Tests for PUT /api/v1/user/company."""

    @pytest.mark.asyncio
    async def test_set_company_success(self, client: AsyncClient, admin_user: User, admin_token: str, test_session):
        """Should set active company."""
        # Create a second company for the admin to switch to
        company = Company(name="Secondary Company", inn="7701987654", legal_form="АО")
        test_session.add(company)
        await test_session.flush()

        from app.models.user_company import UserCompany
        uc = UserCompany(user_id=admin_user.id, company_id=company.id, role="member")
        test_session.add(uc)
        await test_session.flush()

        response = await client.put(
            "/api/v1/user/company",
            json={"company_id": company.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Active company set successfully"
        assert data["active_company"]["id"] == company.id
        assert data["active_company"]["name"] == "Secondary Company"

    @pytest.mark.asyncio
    async def test_set_company_not_member(self, client: AsyncClient, admin_token: str, demo_company: Company):
        """Should return 401 if user is not a member."""
        # admin_user is not a member of demo_company
        response = await client.put(
            "/api/v1/user/company",
            json={"company_id": demo_company.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Service raises ForbiddenException (403) for non-membership
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_set_company_not_found(self, client: AsyncClient, admin_token: str):
        """Should return 404 for non-existent company."""
        response = await client.put(
            "/api/v1/user/company",
            json={"company_id": 99999},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
