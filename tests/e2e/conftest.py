"""
Playwright E2E Test Suite — Shared Fixtures
Requires a running backend at http://127.0.0.1:8001
Start uvicorn before running: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
"""
import os
import sys
import time
import httpx
import pytest

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")

# Admin credentials from env (set in .env or CI)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@icp-solution.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "ICP-SECURE-2026-ADMIN")

# Test user credentials — seeded automatically by the `authenticated_page` fixture
TEST_USER_EMAIL = os.getenv("E2E_TEST_EMAIL", "e2e-test-user@playwright.dev")
TEST_USER_PASSWORD = os.getenv("E2E_TEST_PASSWORD", "E2eTestPass123!")
TEST_USER_NAME = "E2E Test User"

# Dedicated E2E admin account — seeded automatically, never the real admin.
# Self-registration creates role "user", which /api/auth/admin_login rejects,
# so the account is seeded the same way dev_tools/create_admin_cli.py does it.
E2E_ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "e2e-admin@icp-solution.com")
E2E_ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "E2eAdminPass123!")


# ── Session-scoped fixtures ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url(browser):
    """One origin for every engine: the loopback URL from E2E_BASE_URL.

    WebKit on Windows used to be pushed to the machine's LAN IP because that
    Playwright build could not open TCP connections to 127.0.0.1. It can, and
    the LAN IP is a worse origin: http://192.168.x.x is not a secure context,
    so navigator.serviceWorker is undefined there (measured in all three
    engines) and the offline and parity tests were asserting a capability the
    origin cannot have. Loopback is secure everywhere, so every engine now
    tests the same origin — which also makes a pass mean the same thing on
    each of them.
    """
    return BASE_URL


@pytest.fixture(scope="session")
def admin_credentials():
    return {
        "email": E2E_ADMIN_EMAIL,
        "password": E2E_ADMIN_PASSWORD,
        "invite_code": ADMIN_INVITE_CODE,
    }


@pytest.fixture(scope="session")
def test_user_token():
    """
    Session-scoped fixture that ensures a test user exists in the DB and
    returns a valid JWT access_token for that user.

    Strategy:
      1. Attempt direct login with the test credentials.
      2. If login fails (user not registered), call /api/auth/register to get
         the OTP, then /api/auth/verify-email to confirm. Then login again.
      3. Returns the access_token string, or None if the backend is unreachable.
    """
    login_url = f"{BASE_URL}/api/auth/login"
    register_url = f"{BASE_URL}/api/auth/register"
    verify_url = f"{BASE_URL}/api/auth/verify-email"

    def do_login():
        r = httpx.post(
            login_url,
            data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        return None

    try:
        # 1. Try login first (user may already exist from a previous run)
        token = do_login()
        if token:
            return token

        # 2. Register the test user
        reg_r = httpx.post(
            register_url,
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME,
            },
            timeout=15,
        )
        if reg_r.status_code not in (200, 201):
            # Registration failed — could be "already registered" race condition
            token = do_login()
            return token

        otp = reg_r.json().get("otp")
        if not otp:
            return None

        # 3. Verify email with the OTP the backend returned directly
        verify_r = httpx.post(
            verify_url,
            json={"email": TEST_USER_EMAIL, "otp": otp},
            timeout=15,
        )
        if verify_r.status_code != 200:
            return None

        # 4. Now login to get the token
        time.sleep(0.5)
        return do_login()

    except Exception as exc:
        print(f"[conftest] test_user_token fixture error: {exc}")
        return None


@pytest.fixture(scope="session")
def admin_user_token():
    """
    Session-scoped fixture that seeds a dedicated E2E admin account and
    returns a valid admin JWT for it.

    Strategy:
      1. Attempt /api/auth/admin_login directly (account may already exist
         from a previous run).
      2. If that fails, seed the account via direct DB access — mirroring
         dev_tools/create_admin_cli.py: upsert with role "admin" and a known
         password hash, resetting any stale lockout counters — then login again.
      3. Returns the access_token string, or None if seeding is impossible.
    """
    def do_admin_login():
        r = httpx.post(
            f"{BASE_URL}/api/auth/admin_login",
            data={
                "username": E2E_ADMIN_EMAIL,
                "password": E2E_ADMIN_PASSWORD,
                "invite_code": ADMIN_INVITE_CODE,
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        return None

    try:
        token = do_admin_login()
        if token:
            return token

        # Seed / repair the E2E admin via direct DB access
        from pymongo import MongoClient
        from backend.core.config import MONGO_URI, DB_NAME
        from backend.core.security import hash_password
        from backend.services.utils import get_malaysia_time

        if not MONGO_URI:
            # Loud warning: a silent None here surfaces as opaque skips later.
            # CI must provide MONGO_URI (and matching DB_NAME) to the pytest
            # process — see job-level env in build_apps.yml.
            print(
                "WARNING: MONGO_URI not set in the pytest process — cannot seed "
                "the E2E admin account. Set MONGO_URI/DB_NAME env (same values "
                "as the backend) or provide a .env file."
            )
            return None
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        try:
            users = client[DB_NAME]["users"]
            now = get_malaysia_time()
            if users.find_one({"email": E2E_ADMIN_EMAIL}):
                users.update_one(
                    {"email": E2E_ADMIN_EMAIL},
                    {
                        "$set": {
                            "password_hash": hash_password(E2E_ADMIN_PASSWORD),
                            "role": "admin",
                            "failed_invite_attempts": 0,
                        },
                        "$unset": {"lockout_until": "", "invite_lockout_until": ""},
                    },
                )
            else:
                users.insert_one({
                    "email": E2E_ADMIN_EMAIL,
                    "password_hash": hash_password(E2E_ADMIN_PASSWORD),
                    "role": "admin",
                    "created_at": now,
                    "weekly_question_count": 0,
                    "weekly_reset_at": now,
                    "daily_resume_count": 0,
                    "daily_interview_count": 0,
                    "daily_assist_count": 0,
                    "daily_reset_at": now,
                    "last_login_ip": None,
                })
        finally:
            client.close()

        return do_admin_login()
    except Exception as exc:
        print(f"[conftest] admin_user_token fixture error: {exc}")
        return None


# ── Per-test fixtures ──────────────────────────────────────────────────────

def _validate_token_remote(token):
    """Validate a JWT against /api/auth/me. Retries once on connection
    errors — under a full-suite burst, localhost connects can transiently
    fail (TIME_WAIT pressure) while the backend is perfectly healthy."""
    for attempt in range(2):
        try:
            r = httpx.get(
                f"{BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            return r.status_code == 200
        except httpx.HTTPError:
            if attempt == 0:
                time.sleep(1.5)
                continue
            return False
    return False

@pytest.fixture
def drive_vue():
    """Put a page into a state by changing its Vue instance, as the app does.

    Overlays and error banners are v-if'd on component data, so sampling their
    markup at rest asserts on a document that does not contain them — a test
    that can never fail. Merging values into the live instance reaches the same
    state the app's own handlers reach, without copying the template into the
    assertion.

    Returns a callable that takes the page and the data keys to set, and False
    when no Vue application is mounted on #app.
    """

    def _drive(page, **values):
        # The container gets __vue_app__ before the root instance exists, so wait
        # for a resolvable proxy rather than for the mount to be announced.
        page.wait_for_function(
            """() => {
                 const host = document.querySelector('#app');
                 if (!host) return false;
                 const app = host.__vue_app__;
                 const inst = (app && app._instance) || (host._vnode && host._vnode.component);
                 return !!(inst && inst.proxy);
             }""",
            timeout=15000,
        )
        return page.evaluate(
            """(state) => {
                 const host = document.querySelector('#app');
                 const app = host.__vue_app__;
                 // app._instance is null on this app's mount path; the container's
                 // root vnode holds the same instance.
                 const instance = (app && app._instance) || (host._vnode && host._vnode.component);
                 const vm = instance && instance.proxy;
                 if (!vm) return false;
                 Object.assign(vm, state);
                 return true;
             }""",
            values,
        )

    return _drive


@pytest.fixture
def authenticated_page(browser, test_user_token):
    """
    A Playwright page pre-authenticated as the E2E test user.

    Validates the JWT against /api/auth/me, then injects it into localStorage
    via an init script so it is present before any page script runs
    (app.min.js reads localStorage synchronously at parse time). Tests that
    require auth should use this fixture instead of `page`.

    Skips if no valid token could be obtained (backend unreachable or
    registration failed).
    """
    if not test_user_token:
        pytest.skip("No test user token available — backend may be down or registration failed")

    # Cheap server-side validation before touching the browser
    if not _validate_token_remote(test_user_token):
        pytest.skip("Test user token rejected by /api/auth/me")

    # Dedicated context with an init script so the token exists before any
    # page script executes — no need to hop through login.html first.
    # (JWT chars are URL-safe, so direct interpolation is safe here.)
    context = browser.new_context()
    context.add_init_script(
        f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def authenticated_admin_page(browser, admin_user_token):
    """
    Same as `authenticated_page`, but signed in as the seeded E2E admin.
    The admin portal JS gates on window.icp.state.token (localStorage
    "token"), so the same init-script injection works.

    Skips if the admin token could not be obtained or is rejected.
    """
    if not admin_user_token:
        pytest.skip("No admin token available — backend may be down or admin seeding failed")

    if not _validate_token_remote(admin_user_token):
        pytest.skip("Admin token rejected by /api/auth/me")

    context = browser.new_context()
    context.add_init_script(
        f"try {{ localStorage.setItem('token', '{admin_user_token}'); }} catch (e) {{ }}"
    )
    page = context.new_page()
    yield page
    context.close()


# ── Seeded resume submissions ──────────────────────────────────────────────
# The admin suites asserted on whatever the database already held. On a
# developer's machine that is a queue with submissions in it; on a fresh CI
# database it is an empty table, so every row assertion there waited 25 s and
# timed out while passing locally. These rows are created for the test, carry
# dates the tests know, and are removed again.


@pytest.fixture(scope="session", autouse=True)
def sweep_stale_seeds():
    """Delete rows a killed run left behind, before the first test reads them.

    The seeding fixtures remove what they insert, but insert_many writes until
    it raises: a failure partway through leaves rows whose ids were never
    returned. Those rows belong to the same account the dashboard suites sign
    in as, so the next run shows a submission nobody uploaded — and the consent
    check that sits beside the upload control is gone with it. Sweeping by
    marker at session start is what makes a killed run harmless to the next.
    """
    from pymongo import MongoClient
    from backend.core.config import MONGO_URI, DB_NAME

    if not MONGO_URI:
        return

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        try:
            for collection, marker in (
                ("resumes", "seeded_resumes"),
                ("interviews", "test_history_view"),
            ):
                client[DB_NAME][collection].delete_many({"test_seed": marker})
        finally:
            client.close()
    except Exception as exc:
        # A sweep that cannot run must not fail the session: the seeding
        # fixtures report their own database problems, with better messages.
        print(f"[conftest] stale-seed sweep skipped: {exc}")


SEEDED_RESUMES = [
    {
        "key": "pending_pdf",
        "filename": "e2e-seeded-pending.pdf",
        "status": "pending",
        "mime": "application/pdf",
        "hours_ago": 1,
        "tags": ["e2e-seed", "backend"],
        "notes": "",
        "has_file": True,
    },
    {
        "key": "reviewed_pdf",
        "filename": "e2e-seeded-reviewed.pdf",
        "status": "reviewed",
        "mime": "application/pdf",
        "hours_ago": 2,
        "tags": ["e2e-seed"],
        "notes": "Reviewed in the E2E suite.",
        "has_file": True,
    },
    {
        "key": "pending_docx",
        "filename": "e2e-seeded-pending.docx",
        "status": "pending",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "hours_ago": 3,
        "tags": [],
        "notes": "",
        "has_file": False,
    },
]

# Multi-paragraph prose, because the text preview is asserted to read like
# paragraphs rather than like a run-on line. The experience block wraps
# mid-sentence the way a PDF column does: a line that ends in a full stop is
# a paragraph boundary, so a seed that stopped at one would never exercise the
# merge that the prose tests are about.
SEEDED_RESUME_TEXT = (
    "SUMMARY\n"
    "Backend engineer with six years building Python services for payments.\n\n"
    "EXPERIENCE\n"
    "Led the migration of a billing service to FastAPI, cutting p95 latency\n"
    "from 900 ms to 210 ms without downtime by moving the slow path behind a\n"
    "queue and replaying the backlog.\n\n"
    "EDUCATION\n"
    "BSc Computer Science, University of Malaya.\n"
)


def _minimal_pdf(label):
    """A valid one-page PDF, so the viewer has a real document to embed.

    Built here rather than shipped as a binary fixture: the cross-reference
    offsets have to match the bytes, and computing them is the only way they
    stay correct when the label changes.
    """
    stream = b"BT /F1 12 Tf 20 100 Td (" + label + b") Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref_at
    )
    return bytes(out)


@pytest.fixture(scope="module")
def seeded_resumes(test_user_token):
    """Three submissions for the admin queue, removed when the module ends.

    Returns the ids by key, so a test that needs a document with a real file
    asks for one instead of scanning the queue and skipping when the search
    comes back empty.
    """
    import base64
    import uuid
    from datetime import datetime, timedelta, timezone

    if not test_user_token:
        pytest.skip("No test user token — backend unreachable")

    from pymongo import MongoClient
    from backend.core.config import MONGO_URI, DB_NAME

    if not MONGO_URI:
        pytest.skip("MONGO_URI not configured in the pytest process")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    inserted = []
    marker = "seeded_resumes"
    try:
        db = client[DB_NAME]
        try:
            user = db["users"].find_one({"email": TEST_USER_EMAIL})
        except Exception as exc:
            pytest.skip(f"could not read {DB_NAME} to seed resumes: {exc}")
        if not user:
            host = MONGO_URI.rsplit("@", 1)[-1].split("/")[0]
            pytest.skip(
                f"E2E user {TEST_USER_EMAIL} is not in {DB_NAME} on {host} — the "
                f"pytest process and the running app must agree on the database"
            )

        now = datetime.now(timezone.utc)
        docs = []
        for spec in SEEDED_RESUMES:
            doc = {
                "user_id": str(user["_id"]),
                # resume_id is uniquely indexed, so seeded rows cannot all
                # share the null value a real submission never has.
                "resume_id": f"e2e-seed-{spec['key']}-{uuid.uuid4().hex[:10]}",
                "filename": spec["filename"],
                "status": spec["status"],
                "tags": list(spec["tags"]),
                "notes": spec["notes"],
                "text": SEEDED_RESUME_TEXT,
                "mime_type": spec["mime"],
                "created_at": now - timedelta(hours=spec["hours_ago"]),
                "test_seed": marker,
            }
            if spec["has_file"]:
                doc["file_b64"] = base64.b64encode(
                    _minimal_pdf(spec["key"].encode())
                ).decode("ascii")
            docs.append(doc)

        inserted = list(db["resumes"].insert_many(docs).inserted_ids)
        yield {
            spec["key"]: str(_id) for spec, _id in zip(SEEDED_RESUMES, inserted)
        }
    finally:
        # By marker as well as by id: insert_many inserts until it raises, so a
        # partial failure leaves rows that the id list never saw.
        client[DB_NAME]["resumes"].delete_many(
            {"$or": [{"_id": {"$in": inserted}}, {"test_seed": marker}]}
        )
        client.close()
