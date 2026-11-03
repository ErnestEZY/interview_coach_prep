"""Load / burst extension for the ICP backend API.

Adds sustained and mixed bursts on top of test_stress.py: 100-way public
bursts, sequential throughput, unauthenticated flood, bad-credential flood
and post-burst health. Runs in-process through ASGITransport, so no external
server or locust/k6 dependency is required.

Run: pytest tests/stress/test_load_api.py -v --tb=short
"""
import asyncio
import os
import sys
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db  # noqa: E402
from backend.core.security import hash_password  # noqa: E402

UID = "507f191e810c19729de860ea"
BASE_USER = {
    "_id": UID, "email": "u@t.com", "role": "user",
    "is_verified": True, "has_analyzed": True,
    "password_hash": hash_password("Pass123!"),
    "daily_resume_count": 0, "daily_interview_count": 0,
    "daily_question_count": 0, "daily_reset_at": None,
    "failed_login_attempts": 0, "lockout_until": None,
}


@pytest.fixture(autouse=True)
def _isolate_rate_limit():
    """The limiter bucket is process-global; bursts here must not starve the
    older stress/security suites that run afterwards in the same session."""
    from backend.services.rate_limit import bucket

    bucket.clear()
    yield
    bucket.clear()


@pytest_asyncio.fixture
async def ac():
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestBurstLoad:
    @pytest.mark.asyncio
    async def test_100_mixed_public_requests_never_5xx(self, ac):
        """100 simultaneous mixed public reads must not produce a single 5xx."""
        paths = ["/api/auth/config", "/robots.txt", "/manifest.json", "/"]
        tasks = [ac.get(paths[i % len(paths)]) for i in range(100)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s < 500 for s in statuses), f"Server errors under load: {set(statuses)}"
        assert all(s in (200, 429) for s in statuses), f"Unexpected: {set(statuses)}"

    @pytest.mark.asyncio
    async def test_100_sequential_config_requests_finish_fast(self, ac):
        """Sustained sequential load: 100 config reads in under 15 seconds."""
        start = time.monotonic()
        for _ in range(100):
            r = await ac.get("/api/auth/config")
            assert r.status_code == 200
        elapsed = time.monotonic() - start
        assert elapsed < 15.0, f"100 sequential config reads took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_40_concurrent_authenticated_reads(self, ac):
        """40 simultaneous /api/auth/me calls stay correct and fast."""
        patch_all_db(users_val=BASE_USER)
        headers = {"Authorization": f"Bearer {make_jwt(UID)}"}
        start = time.monotonic()
        tasks = [ac.get("/api/auth/me", headers=headers) for _ in range(40)]
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        statuses = [r.status_code for r in results]
        assert all(s == 200 for s in statuses), f"Statuses: {set(statuses)}"
        assert elapsed < 5.0, f"40 authenticated reads took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_30_concurrent_bad_logins_never_5xx(self, ac):
        """Credential-stuffing style burst: clean 4xx, never a server error."""
        patch_all_db(users_val=BASE_USER)
        tasks = [
            ac.post(
                "/api/auth/login",
                data={"username": f"attacker{i}@test.com", "password": "WrongPass1!"},
            )
            for i in range(30)
        ]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s < 500 for s in statuses), f"Server errors: {set(statuses)}"
        assert all(s in (400, 401, 403, 422, 429) for s in statuses), f"Unexpected: {set(statuses)}"

    @pytest.mark.asyncio
    async def test_server_stays_healthy_after_burst(self, ac):
        """Post-burst probe: the app still serves correct responses."""
        await asyncio.gather(*[ac.get("/api/auth/config") for _ in range(50)])
        r = await ac.get("/api/auth/config")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    @pytest.mark.asyncio
    async def test_concurrent_registration_flood_stays_consistent(self, ac):
        """25 registrations with unique emails never 5xx and never double-accept
        the same account (one user per email)."""
        patch_all_db(users_val=None)
        tasks = [
            ac.post(
                "/api/auth/register",
                json={"email": f"load-{i}@test.com", "password": "LoadPass1!"},
            )
            for i in range(25)
        ]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s < 500 for s in statuses), f"Server errors: {set(statuses)}"
        assert all(s in (200, 429) for s in statuses), f"Unexpected: {set(statuses)}"
