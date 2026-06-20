"""
Tests for auth endpoints: register, verify-registration, login, verify-login, refresh, me, logout.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Should register a new user and return 201."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@test.ru"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Verification code sent to email"
        assert data["code_length"] == 6

    @pytest.mark.asyncio
    async def test_register_duplicate_verified(self, client: AsyncClient, admin_user: User):
        """Should return 409 if email already registered and verified."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "admin@test.ru"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "CONFLICT"
        assert data["detail"]["field"] == "email"

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Should return 422 for invalid email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "invalid"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_empty_email(self, client: AsyncClient):
        """Should return 422 for empty email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": ""},
        )
        assert response.status_code == 422


class TestVerifyRegistration:
    """Tests for POST /api/v1/auth/verify-registration."""

    @pytest.mark.asyncio
    async def test_verify_registration_success(self, client: AsyncClient, test_session):
        """Should verify registration with valid code."""
        from sqlalchemy import select
        from app.models.verification_code import VerificationCode

        email = "verify@test.ru"
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )

        # Get the code from DB
        stmt = (
            select(VerificationCode)
            .where(VerificationCode.email == email, VerificationCode.purpose == "registration")
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await test_session.execute(stmt)
        code_obj = result.scalar_one()

        # Now verify
        response = await client.post(
            "/api/v1/auth/verify-registration",
            json={"email": email, "code": code_obj.code},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Email verified successfully"
        assert data["verified"] is True

    @pytest.mark.asyncio
    async def test_verify_registration_wrong_code(self, client: AsyncClient, test_session):
        """Should return 400 for wrong code."""
        from app.services.code_service import CodeService

        # Register first
        email = "wrongcode@test.ru"
        await client.post("/api/v1/auth/register", json={"email": email})

        cs = CodeService()
        code = cs.generate_code()

        response = await client.post(
            "/api/v1/auth/verify-registration",
            json={"email": email, "code": code},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] in ("UNAUTHORIZED",)

    @pytest.mark.asyncio
    async def test_verify_registration_user_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent user."""
        response = await client.post(
            "/api/v1/auth/verify-registration",
            json={"email": "nonexistent@test.ru", "code": "123456"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, admin_user: User):
        """Should return 200 for verified user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ru"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Verification code sent to email"

    @pytest.mark.asyncio
    async def test_login_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.ru"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_login_not_verified(self, client: AsyncClient, test_session):
        """Should return 403 for unverified user."""
        # Create unverified user
        user = User(email="unverified@test.ru", is_verified=False)
        test_session.add(user)
        await test_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "unverified@test.ru"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "FORBIDDEN"


class TestVerifyLogin:
    """Tests for POST /api/v1/auth/verify-login."""

    @pytest.mark.asyncio
    async def test_verify_login_success_sets_cookie(
        self, client: AsyncClient, admin_user: User, test_session
    ):
        """Should return JWT tokens and set refresh_token as httpOnly cookie."""
        from sqlalchemy import select
        from app.models.verification_code import VerificationCode

        email = "admin@test.ru"
        # Initiate login
        await client.post("/api/v1/auth/login", json={"email": email})

        # Get the code from DB
        stmt = (
            select(VerificationCode)
            .where(VerificationCode.email == email, VerificationCode.purpose == "login")
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await test_session.execute(stmt)
        code_obj = result.scalar_one()
        code = code_obj.code

        response = await client.post(
            "/api/v1/auth/verify-login",
            json={"email": email, "code": code},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        # By default, refresh_token should NOT be in body
        assert "refresh_token" not in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

        # Check that refresh_token cookie is set via Set-Cookie header
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie_header
        assert "httponly" in set_cookie_header.lower()
        assert "max-age=" in set_cookie_header.lower()

        # Extract refresh token from Set-Cookie header and verify it
        import re
        match = re.search(r"refresh_token=([^;]+)", set_cookie_header)
        assert match is not None
        refresh_token = match.group(1)
        payload = decode_token(refresh_token)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert int(payload["sub"]) == admin_user.id

        # Verify access token is valid
        payload = decode_token(data["access_token"])
        assert payload is not None
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_verify_login_return_refresh_token_in_body(
        self, client: AsyncClient, admin_user: User, test_session
    ):
        """Should include refresh_token in body when ?return_refresh_token=true."""
        from sqlalchemy import select
        from app.models.verification_code import VerificationCode

        email = "admin@test.ru"
        await client.post("/api/v1/auth/login", json={"email": email})

        stmt = (
            select(VerificationCode)
            .where(VerificationCode.email == email, VerificationCode.purpose == "login")
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await test_session.execute(stmt)
        code_obj = result.scalar_one()
        code = code_obj.code

        response = await client.post(
            "/api/v1/auth/verify-login?return_refresh_token=true",
            json={"email": email, "code": code},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data  # Should be in body with query param
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_verify_login_wrong_code(self, client: AsyncClient, admin_user: User):
        """Should return 400 for wrong code."""
        email = "admin@test.ru"
        await client.post("/api/v1/auth/login", json={"email": email})

        response = await client.post(
            "/api/v1/auth/verify-login",
            json={"email": email, "code": "000000"},
        )
        assert response.status_code == 400


class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success_from_cookie(
        self, client: AsyncClient, admin_user: User
    ):
        """Should return new access token when refresh token is in cookie."""
        refresh_token = create_refresh_token(admin_user.id)

        client.cookies.set("refresh_token", refresh_token)
        response = await client.post(
            "/api/v1/auth/refresh",
            json={},  # No body token, using cookie
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data  # Rotated refresh token
        assert data["expires_in"] == 900

        # Verify a new cookie was set (Set-Cookie header present)
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie_header
        # Max-age should be present (7 days in seconds)
        assert "max-age=" in set_cookie_header.lower()
        # httponly flag should be set
        assert "httponly" in set_cookie_header.lower()

    @pytest.mark.asyncio
    async def test_refresh_success_from_body(
        self, client: AsyncClient, admin_user: User
    ):
        """Should return new access token when refresh token is in body (backward compat)."""
        refresh_token = create_refresh_token(admin_user.id)

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] == 900

        # Cookie should also be set
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie_header

    @pytest.mark.asyncio
    async def test_refresh_no_token(self, client: AsyncClient):
        """Should return 401 when no refresh token provided."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Should return 401 for invalid refresh token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, client: AsyncClient):
        """Should clear the refresh_token cookie."""
        # Set a fake refresh cookie first
        client.cookies.set("refresh_token", "some-fake-token")

        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out"

        # The response should have a set-cookie header that clears the cookie
        # (httpx response.cookies might still show it, but set-cookie header will have past expiry)
        set_cookie = response.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        # Should have httponly flag
        assert "httponly" in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_logout_without_cookie(self, client: AsyncClient):
        """Should still return success even without a cookie."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out"


class TestMe:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_me_success(self, client: AsyncClient, admin_user: User, admin_token: str):
        """Should return user profile."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.ru"
        assert data["is_verified"] is True
        assert data["id"] == admin_user.id

    @pytest.mark.asyncio
    async def test_me_no_token(self, client: AsyncClient):
        """Should return 401 without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        """Should return 401 with invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
