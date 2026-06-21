"""
Test configuration and fixtures for SRP backend tests.
"""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany
from app.core.security import create_access_token
from app.core.rate_limiter import InMemoryRateLimiter, RateLimiter
from app.services.cache_service import CacheService
from app.services.email_service import ConsoleEmailService

# Use in-memory SQLite for tests
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create a test engine (session-scoped event loop via loop_scope)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh test session for each test."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with overridden dependencies."""

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.email_service = ConsoleEmailService()
    # Use in-memory rate limiter for tests (Redis not available)
    app.state.rate_limiter = RateLimiter(redis_service=None)
    app.state.rate_limiter._memory = InMemoryRateLimiter(max_attempts=100, window_seconds=1)
    app.state.cache_service = CacheService(redis_service=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(test_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(email="admin@test.ru", is_verified=True)
    test_session.add(user)
    await test_session.flush()
    company = Company(name="Test Company", inn="7701123456", legal_form="ООО")
    test_session.add(company)
    await test_session.flush()
    uc = UserCompany(user_id=user.id, company_id=company.id, role="admin")
    test_session.add(uc)
    user.active_company_id = company.id
    await test_session.flush()
    return user


@pytest_asyncio.fixture
async def regular_user(test_session: AsyncSession) -> User:
    """Create a regular (non-admin) user for testing."""
    user = User(email="user@test.ru", is_verified=True)
    test_session.add(user)
    await test_session.flush()
    return user


@pytest_asyncio.fixture
async def demo_company(test_session: AsyncSession) -> Company:
    """Create a demo company for testing."""
    company = Company(name="Demo Company", inn="7701987654", legal_form="АО")
    test_session.add(company)
    await test_session.flush()
    return company


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate an access token for the admin user."""
    return create_access_token(admin_user.id)


@pytest.fixture
def user_token(regular_user: User) -> str:
    """Generate an access token for a regular user."""
    return create_access_token(regular_user.id)
