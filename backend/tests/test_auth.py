import os
import pytest
from httpx import AsyncClient
from backend.main import app

if os.getenv("RUN_DB_TESTS", "0") != "1":
    pytest.skip("Skipping DB-dependent tests", allow_module_level=True)

@pytest.mark.asyncio
async def test_register_and_login():
    email = "user1@example.com"
    password = "Pass123!"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={"email": email, "password": password})
        assert r.status_code == 200
        token = r.json()["access_token"]
        assert token
        r2 = await ac.post("/api/auth/login", data={"username": email, "password": password})
        assert r2.status_code == 200
        assert r2.json()["access_token"]
