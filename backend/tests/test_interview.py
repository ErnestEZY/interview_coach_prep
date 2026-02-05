import os
import pytest
from httpx import AsyncClient
from backend.main import app

if os.getenv("RUN_DB_TESTS", "0") != "1":
    pytest.skip("Skipping DB-dependent tests", allow_module_level=True)

async def get_token(ac: AsyncClient):
    email = "user2@example.com"
    password = "Pass123!"
    r = await ac.post("/api/auth/register", json={"email": email, "password": password})
    return r.json()["access_token"]

@pytest.mark.asyncio
async def test_start_interview():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        token = await get_token(ac)
        r = await ac.post("/api/interview/start", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "session_id" in r.json()
