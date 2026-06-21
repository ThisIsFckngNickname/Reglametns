"""
Tests for auth endpoints: register, login, refresh, me, logout.
Uses email + password authentication.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.security import decode_token


TEST_EMAIL = "testauth@test.ru"
TEST_PASSWORD = "testpass123"


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a test user and return credentials."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201
    return {"email": TEST_EMAIL, "password": TEST_PASSWORD}


@pytest_asyncio.fixture
async def logged_in_user(client: AsyncClient, registered_user: dict) -> dict:
    """Login as the registered test user and return tokens + credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json=registered_user,
    )
    assert response.status_code == 200
    data = response.json()
    return {**registered_user, **data}


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Should register a new user and return 201 with tokens."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    @pytest.mark.asyncio
    async def test_register_duplicate(self, client: AsyncClient):
        """Should return 409 if email already exists."""
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        # Now try duplicate
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Should return 422 for invalid email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "invalid", "password": TEST_PASSWORD},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Should return 422 for password less than 6 chars."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "short@test.ru", "password": "123"},
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, registered_user: dict):
        """Should login with correct credentials and return tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json=registered_user,
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, registered_user: dict):
        """Should return 401 for wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "wrongpassword"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Should return 404 for non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.ru", "password": "somepass"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_login_missing_password(self, client: AsyncClient):
        """Should return 422 if password is missing."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL},
        )
        assert response.status_code == 422


class TestGetMe:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client: AsyncClient, logged_in_user: dict):
        """Should return user profile with valid token."""
        token = logged_in_user["access_token"]
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == TEST_EMAIL
        assert data["is_verified"] is True
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Should return 401 without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Should return 401 with invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401


class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient, logged_in_user: dict):
        """Should refresh access token with valid refresh token."""
        refresh_token = logged_in_user["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Should return 401 with invalid refresh token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid"},
        )
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """Should return 200 on logout."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out"


class TestTokenValidation:
    """Tests for JWT token validation."""

    @pytest.mark.asyncio
    async def test_access_token_format(self, client: AsyncClient, logged_in_user: dict):
        """Access token should have correct type claim."""
        token = logged_in_user["access_token"]
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"
        assert "sub" in payload

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client: AsyncClient):
        """Should return 401 for expired token."""
        from datetime import datetime, timedelta, timezone

        import jwt

        from app.config import settings

        # Token expired 1 hour ago
        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "999",
            "type": "access",
            "exp": expire,
        }
        expired_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
