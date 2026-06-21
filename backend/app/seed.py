"""
Seed script: creates an admin user and a demo holding for development.
Run with: python -m app.seed
"""

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session
from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany

logger = logging.getLogger(__name__)


async def seed() -> None:
    """Create seed data: admin user + demo company."""
    async with async_session() as db:
        try:
            # Check if seed data already exists
            result = await db.execute(
                select(Company).where(Company.name == "ООО Демо-Холдинг")
            )
            if result.scalar_one_or_none():
                logger.info("Seed data already exists. Skipping.")
                await db.commit()
                return

            # Create demo company
            company = Company(
                name="ООО Демо-Холдинг",
                inn="7701123456",
                legal_form="ООО",
            )
            db.add(company)
            await db.flush()
            logger.info(f"Created company: {company.name} (id={company.id})")

            # Create admin user
            user = User(
                email="admin@gmail.com",
                is_verified=True,
                active_company_id=company.id,
            )
            user.set_password("Admin12+")
            db.add(user)
            await db.flush()
            logger.info(f"Created user: {user.email} (id={user.id})")

            # Create user_company link with admin role
            user_company = UserCompany(
                user_id=user.id,
                company_id=company.id,
                role="admin",
            )
            db.add(user_company)
            await db.flush()
            logger.info(
                f"Created user_company: user={user.id}, company={company.id}, role=admin"
            )

            await db.commit()
            logger.info("Seed completed successfully.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Seed failed: {e}")
            raise
        finally:
            await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
