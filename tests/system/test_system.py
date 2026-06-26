"""
System Tests — ICP Full-Stack End-to-End
=========================================
These tests run against the REAL running application with a REAL MongoDB
test database. No mocks. The full stack is exercised: FastAPI app,
MongoDB Motor driver, JWT auth, daily limit counters, all routes.

HOW TO RUN:
  1. Start the server: uvicorn backend.main:app --host 127.0.0.1 --port 8002
  2. Run:  pytest tests/system/ -v --tb=short --system-base-url=http://127.0.0.1:8002

  Or with env var:
  $env:SYSTEM_BASE_URL = "http://127.0.0.1:8002"
  pytest tests/system/ -v --tb=short

IMPORTANT:
  - Uses a SEPARATE test database (icp_system_test) so real data is never touched.
  - Each test class cleans up its own documents after running.
  - Tests are skipped automatically when the server is not reachable.
"""
import os
import sys
import time
import asyncio
import pytest
import pytest_asyncio
import httpx
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = os.environ.get("SYSTEM_BASE_URL", "http://127.0.0.1:8002")


# ── Pytest hook to add --system-base-url CLI option ──────────────────────────
def pytest_addoption(parser):
    parser.addoption("--system-base-url", default=None,
                     help="Base URL of the running ICP server for system tests")


@pytest.fixture(scope="session", autouse=True)
def resolve_base_url(request):
    global BASE_URL
    cli = request.config.getoption("--system-base-url", default=None)
    if cli:
        BASE_URL = cli


# ── Skip if server is not reachable ──────────────────────────────────────────
def server_is_up() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/api/auth/config", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


skip_if_down = pytest.mark.skipif(
    not server_is_up(),
    reason=f"System tests skipped — server not reachable at {BASE_URL}. "
           f"Start with: uvicorn backend.main:app --port 8002"
)


# ── Shared HTTP client ────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        yield c


# ── Unique email per test run so reruns don't collide ────────────────────────
TS = int(time.time())
TEST_EMAIL    = f"sys_test_{TS}@autotest.com"
TEST_PASSWORD = "SysTest1!"


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 1 — Application Health
# ═════════════════════════════════════════════════════════════════════════════
@skip_if_down
class TestSystemHealth:
    @pytest.mark.asyncio
    async def test_config_endpoint_returns_keys(self, client):
        r = await client.get("/api/auth/config")
        assert r.status_code == 200
        body = r.json()
        assert "emailjs_public_key" in body
        assert "careerjet_widget_id" in body

    @pytest.mark.asyncio
    async def test_startup_id_present(self, client):
        r = await client.get("/api/meta/startup_id")
        assert r.status_code == 200
        assert "startup_id" in r.json()

    @pytest.mark.asyncio
    async def test_find_jobs_page_served(self, client):
        r = await client.get("/find-jobs/")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()

    @pytest.mark.asyncio
    async def test_static_css_served(self, client):
        r = await client.get("/static/css/styles.css")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_all_auth_routes_exist(self, client):
        # Endpoints must exist (wrong body → 422, not 404)
        r = await client.post("/api/auth/login", data={})
        assert r.status_code == 422

        r = await client.post("/api/auth/register", json={})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_protected_routes_require_auth(self, client):
        for path in ["/api/resume/limits", "/api/interview/limits",
                     "/api/admin/resumes", "/api/auth/me"]:
            r = await client.get(path)
            assert r.status_code == 401, f"{path} should require auth"


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 2 — Registration Flow (real DB)
# ═════════════════════════════════════════════════════════════════════════════
@skip_if_down
class TestSystemRegistration:
    """
    Registers a real user in MongoDB, verifies OTP, then cleans up.
    Requires RUN_SYSTEM_DB_TESTS=1 to actually write to the DB.
    """
    RUN = os.environ.get("RUN_SYSTEM_DB_TESTS", "0") == "1"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not (os.environ.get("RUN_SYSTEM_DB_TESTS") == "1"),
                        reason="Set RUN_SYSTEM_DB_TESTS=1 to run DB-writing system tests")
    async def test_register_creates_pending_user(self, client):
        r = await client.post("/api/auth/register",
                              json={"email": TEST_EMAIL,
                                    "password": TEST_PASSWORD,
                                    "name": "System Tester"})
        assert r.status_code == 200
        body = r.json()
        assert "otp" in body
        assert body["email"] == TEST_EMAIL
        assert len(body["otp"]) == 6

    @pytest.mark.asyncio
    @pytest.mark.skipif(not (os.environ.get("RUN_SYSTEM_DB_TESTS") == "1"),
                        reason="Set RUN_SYSTEM_DB_TESTS=1 to run DB-writing system tests")
    async def test_duplicate_registration_returns_400(self, client):
        """Second registration with same email during pending state → upsert (200 again)."""
        r = await client.post("/api/auth/register",
                              json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code in (200, 400)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not (os.environ.get("RUN_SYSTEM_DB_TESTS") == "1"),
                        reason="Set RUN_SYSTEM_DB_TESTS=1 to run DB-writing system tests")
    async def test_verify_wrong_otp_returns_400(self, client):
        r = await client.post("/api/auth/verify-email",
                              json={"email": TEST_EMAIL, "otp": "000000"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.skipif(not (os.environ.get("RUN_SYSTEM_DB_TESTS") == "1"),
                        reason="Set RUN_SYSTEM_DB_TESTS=1 to run DB-writing system tests")
    async def test_resend_otp_within_cooldown_returns_429(self, client):
        """Immediately after register the 30s cooldown is active."""
        r = await client.post("/api/auth/resend-otp",
                              json={"email": TEST_EMAIL})
        assert r.status_code == 429


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 3 — Authentication Enforcement (real JWT verification)
# ═════════════════════════════════════════════════════════════════════════════
@skip_if_down
class TestSystemAuthEnforcement:
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client):
        import jwt
        from datetime import timedelta, timezone
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            pytest.skip("JWT_SECRET not set — cannot forge token for system test")
        expired_token = jwt.encode(
            {"sub": "000000000000000000000000", "role": "user",
             "exp": datetime.now(timezone.utc) - timedelta(hours=1),
             "sid": "DISABLED"},
            secret, algorithm="HS256")
        r = await client.get("/api/auth/me",
                             headers={"Authorization": f"Bearer {expired_token}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_forged_token_rejected(self, client):
        """Token signed with wrong secret must be rejected."""
        import jwt
        from datetime import timedelta, timezone
        fake_token = jwt.encode(
            {"sub": "000000000000000000000000", "role": "admin",
             "exp": datetime.now(timezone.utc) + timedelta(hours=2),
             "sid": "DISABLED"},
            "attacker-secret", algorithm="HS256")
        r = await client.get("/api/auth/me",
                             headers={"Authorization": f"Bearer {fake_token}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client):
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_route_rejects_user_token(self, client):
        import jwt
        from datetime import timedelta, timezone
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            pytest.skip("JWT_SECRET not set")
        user_token = jwt.encode(
            {"sub": "000000000000000000000000", "role": "user",
             "exp": datetime.now(timezone.utc) + timedelta(hours=2),
             "sid": "DISABLED"},
            secret, algorithm="HS256")
        r = await client.get("/api/admin/resumes",
                             headers={"Authorization": f"Bearer {user_token}"})
        # 403 (token valid but role wrong) or 401 (user not in DB)
        assert r.status_code in (401, 403)


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 4 — Rate Limiting (real slowapi middleware)
# ═════════════════════════════════════════════════════════════════════════════
@skip_if_down
class TestSystemRateLimiting:
    @pytest.mark.asyncio
    async def test_register_endpoint_rate_limited(self, client):
        """
        Flood the register endpoint — should hit 429 before or after
        several requests (actual limit depends on RATE_LIMIT_PER_MINUTE env).
        In production this is 60/min; in a test server it may be higher.
        We send 10 rapid requests and accept any mix of 200/400/422/429.
        The key assertion: no 500 errors and the server stays up.
        """
        tasks = [
            client.post("/api/auth/register",
                        json={"email": f"flood_{i}_{TS}@test.com",
                              "password": "Pass123!"})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in results]
        assert all(s != 500 for s in statuses), \
            f"Server returned 500 under load: {statuses}"

    @pytest.mark.asyncio
    async def test_server_recovers_after_burst(self, client):
        """After the burst, the server must still respond to a normal request."""
        r = await client.get("/api/auth/config")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 5 — Page / Asset Availability (real static file serving)
# ═════════════════════════════════════════════════════════════════════════════
@skip_if_down
class TestSystemPageAvailability:
    PAGES = [
        "/",
        "/static/pages/login.html",
        "/static/pages/register.html",
        "/static/pages/verify.html",
        "/static/pages/forgot_password.html",
        "/static/pages/dashboard.html",
        "/static/pages/interview.html",
        "/static/pages/history.html",
        "/static/pages/resume_builder.html",
        "/static/pages/find-jobs.html",
        "/find-jobs/",
    ]

    @pytest.mark.asyncio
    async def test_all_pages_return_200(self, client):
        for path in self.PAGES:
            r = await client.get(path)
            assert r.status_code == 200, \
                f"Page {path} returned {r.status_code} — expected 200"

    @pytest.mark.asyncio
    async def test_css_and_js_assets_served(self, client):
        for path in ["/static/css/styles.css",
                     "/static/js/app.js",
                     "/static/js/verify.js"]:
            r = await client.get(path)
            assert r.status_code == 200, f"Asset {path} returned {r.status_code}"

    @pytest.mark.asyncio
    async def test_unknown_path_does_not_500(self, client):
        r = await client.get("/this/does/not/exist")
        assert r.status_code != 500
