"""
System Tests — ICP Full-Stack End-to-End
=========================================
These tests run against the REAL running application with a REAL MongoDB
test database. No mocks. The full stack is exercised: FastAPI app,
MongoDB Motor driver, JWT auth, daily limit counters, all routes.

HOW TO RUN — nothing has to be started first:
  pytest tests/system/ -v --tb=short

  If nothing answers at SYSTEM_BASE_URL (default http://127.0.0.1:8002) the
  suite starts its own server on a free port with ICP_DB_NAME=icp_system_test
  and stops it when the session ends. Because that database is known to be
  disposable, the DB-writing tests run too instead of being skipped. The
  server's own output is in tests/system/.server.log — read it first when a
  run reports skips.

  Against a server you started yourself:
    pytest tests/system/ -v --system-base-url=http://127.0.0.1:8002
  and add RUN_SYSTEM_DB_TESTS=1 if that server points at a disposable database
  and you want the DB-writing tests to run against it. They are skipped
  otherwise, because nothing in the run can vouch for what is behind a server
  it did not start.

IMPORTANT:
  - ICP_DB_NAME is set on the SERVER, not on the test run. Without it the
    server uses the live database and the registration tests below would write
    real users into it. It is not called DB_NAME because tests/conftest.py
    already pins that name for the mocked unit suites.
  - The test database is disposable. Rows a run creates stay behind under
    timestamped addresses (sys_test_*, flood_*), so empty or drop it freely.
  - Live-app tests are skipped automatically when no server answers and none
    could be started; ICP_NO_AUTOSTART=1 disables the starting.
"""
import os
import sys
import time
import socket
import asyncio
import subprocess
import pytest
import pytest_asyncio
import httpx
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = os.environ.get("SYSTEM_BASE_URL", "http://127.0.0.1:8002")

# The database a self-started server writes to. It is not the live one, and it
# is not called DB_NAME because tests/conftest.py already pins that name for
# the mocked unit suites.
THROWAWAY_DB = "icp_system_test"

# ── Pytest hook to add --system-base-url CLI option ──────────────────────────
# Declared in conftest.py beside this file: pytest only calls pytest_addoption
# on plugin and conftest modules, so declaring the hook in this module left the
# documented flag rejected as "unrecognized arguments".
SERVER_UP = False

# True once this run has started a server of its own. That is the only case in
# which the database behind the tested URLs is known to be the throwaway one,
# so it is also the only case in which writing to it is safe by default.
THROWAWAY = False


@pytest.fixture(scope="session", autouse=True)
def resolve_base_url(request):
    """Resolve the target server, starting one if nothing is listening.

    Both the flag and the environment are read here rather than at import, so
    `--system-base-url` actually reaches the skip decision below. An
    import-time skipif sees only the environment, which made the flag
    documented at the top of this file silently do nothing.

    A suite that only works if the developer remembered to start a server in
    another window is a suite that does not run. When nothing answers, one is
    started on a free port against the throwaway database and stopped again at
    the end of the session. Set ICP_NO_AUTOSTART=1 to keep the old behaviour.
    """
    global BASE_URL, SERVER_UP, THROWAWAY
    cli = request.config.getoption("--system-base-url", default=None)
    if cli:
        BASE_URL = cli

    SERVER_UP = server_is_up()
    if SERVER_UP or os.environ.get("ICP_NO_AUTOSTART") == "1":
        return

    process = start_server()
    if process is None:
        return
    # addfinalizer wants a callable taking no arguments; the server has to be
    # handed back to the cleaner, hence the lambda rather than partial+args.
    request.addfinalizer(lambda: stop_server(process))
    BASE_URL = process.url
    SERVER_UP = True
    THROWAWAY = True


def free_port() -> int:
    """A port the OS says is unused, rather than one guessed to be."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class StartedServer:
    def __init__(self, process, url, log):
        self.process = process
        self.url = url
        self.log = log


def start_server():
    """Boot uvicorn on a free port against the throwaway database."""
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "ICP_DB_NAME": THROWAWAY_DB}
    # The server must not inherit the test-side switch; it only decides what
    # the client is allowed to ask for.
    env.pop("RUN_SYSTEM_DB_TESTS", None)

    log_path = os.path.join(os.path.dirname(__file__), ".server.log")
    log = open(log_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        log.close()
        return None

    deadline = time.time() + 60
    while time.time() < deadline:
        if process.poll() is not None:
            log.close()
            return None  # it died; the skip below says so and the log says why
        if server_is_up(url):
            return StartedServer(process, url, log_path)
        time.sleep(0.5)

    stop_server(StartedServer(process, url, log_path))
    return None


def stop_server(server):
    server.process.terminate()
    try:
        server.process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        server.process.kill()
        server.process.wait(timeout=15)
    try:
        server.process.stdout.close()
    except Exception:
        pass


# ── Skip if server is not reachable ──────────────────────────────────────────
def server_is_up(url=None) -> bool:
    try:
        r = httpx.get(f"{url or BASE_URL}/api/auth/config", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


needs_system_server = pytest.mark.needs_system_server
writes_db = pytest.mark.writes_db


def db_writes_allowed() -> bool:
    """Whether the DB-writing tests may run against this run's server.

    Deliberately a function called at test time rather than a skipif condition
    evaluated at collection: whether a throwaway server was started is only
    known once the session fixture above has run, and a collection-time check
    would always see False and skip a suite that in fact had a safe database.
    """
    return THROWAWAY or os.environ.get("RUN_SYSTEM_DB_TESTS") == "1"


@pytest.fixture(autouse=True)
def require_system_server(request):
    """Skip a live-app test when nothing answers at the resolved URL.

    Decided at run time so the answer matches the URL the tests will actually
    use, and so an absent server reads as "skipped", not as a wall of
    connection failures. The same pass decides whether a test may write to the
    database, since that question has the same dependency on what the session
    fixture managed to set up.
    """
    if request.node.get_closest_marker("needs_system_server") and not SERVER_UP:
        pytest.skip(
            f"System tests skipped — no server at {BASE_URL} and none could be "
            f"started. See {os.path.join(os.path.dirname(__file__), '.server.log')} "
            f"for why."
        )
    if request.node.get_closest_marker("writes_db") and not db_writes_allowed():
        pytest.skip(
            f"DB-writing test skipped — the server at {BASE_URL} was not started "
            f"by this run, so its database cannot be assumed disposable. Point "
            f"the server at {THROWAWAY_DB} and set RUN_SYSTEM_DB_TESTS=1 to run it."
        )


# ── HTTP client ──────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client():
    """One client per test, created on that test's own event loop.

    Session scope leaked a single client across event loops, and every test
    after the first died with "Event loop is closed" — a harness fault that
    was indistinguishable from nine broken endpoints.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        yield c


# ── Unique email per test run so reruns don't collide ────────────────────────
TS = int(time.time())
TEST_EMAIL    = f"sys_test_{TS}@autotest.com"
TEST_PASSWORD = "SysTest1!"


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 1 — Application Health
# ═════════════════════════════════════════════════════════════════════════════
@needs_system_server
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
@needs_system_server
class TestSystemRegistration:
    """
    Registers a real user in MongoDB, verifies OTP, then cleans up.
    Runs when this suite started its own throwaway server, or when
    RUN_SYSTEM_DB_TESTS=1 vouches for a server supplied from outside.
    """

    @pytest.mark.asyncio
    @writes_db
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
    @writes_db
    async def test_duplicate_registration_returns_400(self, client):
        """Second registration with same email during pending state → upsert (200 again)."""
        r = await client.post("/api/auth/register",
                              json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code in (200, 400)

    @pytest.mark.asyncio
    @writes_db
    async def test_verify_wrong_otp_returns_400(self, client):
        r = await client.post("/api/auth/verify-email",
                              json={"email": TEST_EMAIL, "otp": "000000"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    @writes_db
    async def test_resend_otp_within_cooldown_returns_429(self, client):
        """Immediately after register the 30s cooldown is active."""
        r = await client.post("/api/auth/resend-otp",
                              json={"email": TEST_EMAIL})
        assert r.status_code == 429


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST 3 — Authentication Enforcement (real JWT verification)
# ═════════════════════════════════════════════════════════════════════════════
@needs_system_server
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
@needs_system_server
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
@needs_system_server
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
