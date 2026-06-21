"""
Database engine and session factory.

Pool settings are tuned for development:
- pool_size=2: keep 2 persistent connections
- max_overflow=1: allow 1 extra connection under load (total max = 3)
- pool_recycle=1800: recycle connections after 30 minutes
- pool_pre_ping=True: check connection health before each use

For SQLite, these pool settings are ignored by SQLAlchemy (SQLite
uses NullPool by default), so they only take effect with PostgreSQL.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=2,
    max_overflow=1,
    pool_recycle=1800,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
