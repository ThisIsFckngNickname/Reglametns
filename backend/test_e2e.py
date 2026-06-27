import asyncio
import traceback
import httpx
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    body = {"email": "admin@gmail.com", "password": "Admin12+"}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8000/api/v1/auth/login", json=body)
        print(f"Login status: {r.status_code}")
        token = r.json()["access_token"]
        print(f"Token: {token[:30]}...")

        data = {"context": "Регламент по охране труда. Краткий документ: общие положения, требования безопасности, ответственность."}
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r2 = await client.post("http://localhost:8000/api/v1/generator/generate", data=data, headers=headers, timeout=600.0)
            print(f"Generate status: {r2.status_code}")
            print(f"Response: {r2.text[:3000]}")
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()

asyncio.run(test())
