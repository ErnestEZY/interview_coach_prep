"""
Stress / Load Tests — ICP Backend API
Tests: concurrent requests, burst traffic, daily limit enforcement under load.

These are SYNCHRONOUS stress tests using asyncio.gather() to fire multiple
requests at the same time. They do NOT require Locust or k6.

Run: pytest tests/stress/ -v --tb=short -s
"""
import os, sys, asyncio, pytest, pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db

UID = "507f191e810c19729de860ea"
BASE_USER = {"_id": UID, "email": "u@t.com", "role": "user",
             "is_verified": True, "has_analyzed": True,
             "daily_resume_count": 0, "daily_interview_count": 0,
             "daily_question_count": 0, "daily_reset_at": None,
             "failed_login_attempts": 0, "lockout_until": None}


@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestConcurrentRequests:
    @pytest.mark.asyncio
    async def test_20_concurrent_config_requests(self, ac):
        """20 simultaneous GET /api/auth/config — all must return 200."""
        tasks = [ac.get("/api/auth/config") for _ in range(20)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s == 200 for s in statuses), f"Failed statuses: {set(statuses)}"

    @pytest.mark.asyncio
    async def test_20_concurrent_auth_me_requests(self, ac):
        """20 simultaneous authenticated /api/auth/me — all must return 200."""
        patch_all_db(users_val=BASE_USER)
        token = make_jwt(UID)
        headers = {"Authorization": f"Bearer {token}"}
        tasks = [ac.get("/api/auth/me", headers=headers) for _ in range(20)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s == 200 for s in statuses)

    @pytest.mark.asyncio
    async def test_50_concurrent_unauthenticated_requests_return_401(self, ac):
        """50 unauthenticated requests — server must stay stable (no 500)."""
        tasks = [ac.get("/api/resume/limits") for _ in range(50)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s != 500 for s in statuses)
        assert all(s == 401 for s in statuses)


class TestBurstRegistration:
    @pytest.mark.asyncio
    async def test_10_concurrent_registrations_different_emails(self, ac):
        """10 simultaneous registrations with different emails — all must succeed."""
        patch_all_db(users_val=None)   # no existing users
        tasks = [
            ac.post("/api/auth/register",
                    json={"email": f"user{i}@test.com", "password": "Pass123!"})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        # All should succeed (200) or possibly hit rate limit (429)
        assert all(s in (200, 429) for s in statuses), f"Unexpected: {set(statuses)}"

    @pytest.mark.asyncio
    async def test_5_concurrent_duplicate_email_registrations(self, ac):
        """5 concurrent registrations with the SAME email — at least one 400."""
        patch_all_db(users_val={"email": "dup@test.com"})
        tasks = [
            ac.post("/api/auth/register",
                    json={"email": "dup@test.com", "password": "Pass123!"})
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert any(s == 400 for s in statuses), "Expected at least one 400 for duplicate email"


class TestDailyLimitUnderLoad:
    @pytest.mark.asyncio
    async def test_limit_endpoint_stable_under_concurrent_access(self, ac):
        """20 concurrent limit checks — all return valid JSON."""
        patch_all_db(users_val=BASE_USER)
        token = make_jwt(UID)
        tasks = [
            ac.get("/api/resume/limits", headers={"Authorization": f"Bearer {token}"})
            for _ in range(20)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            assert r.status_code == 200
            assert "remaining" in r.json()
            assert "limit" in r.json()

    @pytest.mark.asyncio
    async def test_interview_limits_stable_under_load(self, ac):
        patch_all_db(users_val=BASE_USER)
        token = make_jwt(UID)
        tasks = [
            ac.get("/api/interview/limits", headers={"Authorization": f"Bearer {token}"})
            for _ in range(20)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            assert r.status_code == 200


class TestResponseTimeBaseline:
    @pytest.mark.asyncio
    async def test_config_endpoint_responds_fast(self, ac):
        """Config endpoint should respond in under 2 seconds even under light load."""
        import time
        tasks = [ac.get("/api/auth/config") for _ in range(10)]
        start = time.monotonic()
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"10 config requests took {elapsed:.2f}s — too slow"

    @pytest.mark.asyncio
    async def test_authenticated_route_response_under_load(self, ac):
        """10 authenticated requests must complete in under 3 seconds."""
        import time
        patch_all_db(users_val=BASE_USER)
        token = make_jwt(UID)
        tasks = [
            ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            for _ in range(10)
        ]
        start = time.monotonic()
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, f"10 /me requests took {elapsed:.2f}s"
        assert all(r.status_code == 200 for r in results)
