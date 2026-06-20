"""
Seed script: creates an admin user and a demo holding for development.
Run with: python -m app.seed
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding

logger = logging.getLogger(__name__)


async def seed() -> None:
    """Create seed data: admin user + demo holding."""
    async with async_session() as db:
        try:
            # Check if demo data already exists
            result = await db.execute(select(Holding).where(Holding.name == "ООО Демо-Холдинг"))
            existing_holding = result.scalar_one_or_none()

            result = await db.execute(select(User).where(User.email == "admin@srp.dev"))
            existing_user = result.scalar_one_or_none()

            if existing_holding and existing_user:
                logger.info("Seed data already exists. Skipping.")
                await db.commit()
                return

            # Create demo holding
            if not existing_holding:
                holding = Holding(
                    name="ООО Демо-Холдинг",
                    inn="7701123456",
                    legal_form="ООО",
                )
                db.add(holding)
                await db.flush()
                logger.info(f"Created holding: {holding.name} (id={holding.id})")
            else:
                holding = existing_holding

            # Create admin user
            if not existing_user:
                user = User(
                    email="admin@srp.dev",
                    is_verified=True,
                    active_holding_id=holding.id,
                )
                db.add(user)
                await db.flush()
                logger.info(f"Created user: {user.email} (id={user.id})")
            else:
                user = existing_user

            # Create user_holding link with admin role
            result = await db.execute(
                select(UserHolding).where(
                    UserHolding.user_id == user.id,
                    UserHolding.holding_id == holding.id,
                )
            )
            existing_link = result.scalar_one_or_none()

            if not existing_link:
                user_holding = UserHolding(
                    user_id=user.id,
                    holding_id=holding.id,
                    role="admin",
                )
                db.add(user_holding)
                await db.flush()
                logger.info(f"Created user_holding: user={user.id}, holding={holding.id}, role=admin")

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
