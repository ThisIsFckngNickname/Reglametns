"""
Test configuration and fixtures for SRP backend tests.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding
from app.core.security import create_access_token
from app.core.rate_limiter import InMemoryRateLimiter, RateLimiter
from app.services.cache_service import CacheService
from app.services.email_service import ConsoleEmailService

# Use in-memory SQLite for tests
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test engine."""
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
    holding = Holding(name="Test Holding", inn="7701123456", legal_form="ООО")
    test_session.add(holding)
    await test_session.flush()
    uh = UserHolding(user_id=user.id, holding_id=holding.id, role="admin")
    test_session.add(uh)
    user.active_holding_id = holding.id
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
async def demo_holding(test_session: AsyncSession) -> Holding:
    """Create a demo holding for testing."""
    holding = Holding(name="Demo Holding", inn="7701987654", legal_form="АО")
    test_session.add(holding)
    await test_session.flush()
    return holding


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate an access token for the admin user."""
    return create_access_token(admin_user.id)


@pytest.fixture
def user_token(regular_user: User) -> str:
    """Generate an access token for a regular user."""
    return create_access_token(regular_user.id)
