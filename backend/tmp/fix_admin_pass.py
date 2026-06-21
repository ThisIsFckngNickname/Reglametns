import asyncio
from app.database import async_session
from app.models.user import User
from sqlalchemy import select

async def fix():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == 'admin@srp.dev'))
        user = result.scalar_one_or_none()
        if user:
            user.set_password('admin123')
            await db.commit()
            print(f'Password updated for {user.email}')
            print(f'Check admin123: {user.check_password("admin123")}')
        else:
            print('User admin@srp.dev not found')

asyncio.run(fix())
