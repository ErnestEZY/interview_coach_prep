"""Security Tests — ICP Backend API"""
import os, sys, base64, json, pytest, pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db

UID = "507f191e810c19729de860ea"
BASE_USER = {"_id": UID, "email": "u@t.com", "role": "user", "is_verified": True,
             "has_analyzed": True, "daily_resume_count": 0, "daily_interview_count": 0,
             "daily_question_count": 0, "daily_reset_at": None,
             "failed_login_attempts": 0, "lockout_until": None}

@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Auth Bypass ───────────────────────────────────────────────────────────────
class TestAuthBypass:
    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, ac):
        assert (await ac.get("/api/auth/me")).status_code == 401

    @pytest.mark.asyncio
    async def test_garbage_token_returns_401(self, ac):
        r = await ac.get("/api/auth/me",
                         headers={"Authorization": "Bearer not.valid.token"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, ac):
        patch_all_db(users_val=BASE_USER)
        token = make_jwt(UID, expired=True)
        r = await ac.get("/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_returns_401(self, ac):
        import jwt as _jwt
        tok = _jwt.encode(
            {"sub": UID, "role": "user",
             "exp": datetime.now(timezone.utc) + timedelta(hours=2),
             "sid": "DISABLED"},
            "attacker-secret", algorithm="HS256")
        r = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_tampered_payload_role_escalation_rejected(self, ac):
        """Flip role user→admin without valid signature — must be rejected."""
        original = make_jwt(UID, role="user")
        parts = original.split(".")
        pad = 4 - len(parts[1]) % 4
        decoded = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * pad))
        decoded["role"] = "admin"
        bad_p = base64.urlsafe_b64encode(json.dumps(decoded).encode()).rstrip(b"=").decode()
        tampered = f"{parts[0]}.{bad_p}.{parts[2]}"
        r = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_token_scheme_must_be_bearer(self, ac):
        tok = make_jwt(UID)
        r = await ac.get("/api/auth/me", headers={"Authorization": f"Token {tok}"})
        assert r.status_code == 401


# ── Brute-Force Lockout ───────────────────────────────────────────────────────
class TestBruteForce:
    @pytest.mark.asyncio
    async def test_locked_account_blocked_429(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER,
            "password_hash": hash_password("Pass123!"),
            "lockout_until": datetime.now(timezone.utc) + timedelta(minutes=8)})
        r = await ac.post("/api/auth/login",
                          data={"username": "u@t.com", "password": "Pass123!"})
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_wrong_password_shows_attempt_count(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER,
            "password_hash": hash_password("Real1!"),
            "failed_login_attempts": 2})
        r = await ac.post("/api/auth/login",
                          data={"username": "u@t.com", "password": "Wrong!"})
        assert r.status_code == 401
        assert "3/5" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_fifth_failure_triggers_lockout(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER,
            "password_hash": hash_password("Real1!"),
            "failed_login_attempts": 4})
        r = await ac.post("/api/auth/login",
                          data={"username": "u@t.com", "password": "Wrong!"})
        assert r.status_code == 429


# ── Admin Access Control ──────────────────────────────────────────────────────
class TestAdminAccess:
    @pytest.mark.asyncio
    async def test_non_icp_domain_blocked(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/admin_login",
                          data={"username": "hacker@gmail.com",
                                "password": "Pass123!", "invite_code": "test-invite-123"})
        assert r.status_code == 403
        assert "icp-solution.com" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_user_role_blocked_from_admin_login(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER, "email": "u@icp-solution.com",
                                "role": "user",
                                "password_hash": hash_password("Pass123!")})
        r = await ac.post("/api/auth/admin_login",
                          data={"username": "u@icp-solution.com",
                                "password": "Pass123!", "invite_code": "test-invite-123"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_invite_code_blocked(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER, "email": "adm@icp-solution.com",
                                "role": "admin",
                                "password_hash": hash_password("Pass123!"),
                                "failed_invite_attempts": 0,
                                "invite_lockout_until": None})
        r = await ac.post("/api/auth/admin_login",
                          data={"username": "adm@icp-solution.com",
                                "password": "Pass123!", "invite_code": "wrong-code"})
        assert r.status_code == 403


# ── Injection Prevention ──────────────────────────────────────────────────────
class TestInjectionPrevention:
    @pytest.mark.asyncio
    async def test_nosql_operator_in_email_handled(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/login",
                          data={"username": '{"$gt":""}', "password": "x"})
        assert r.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_sql_injection_treated_as_plain_string(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/login",
                          data={"username": "' OR '1'='1", "password": "' OR '1'='1"})
        assert r.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_xss_in_email_rejected_by_validation(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/register",
                          json={"email": "<script>alert(1)</script>@x.com",
                                "password": "Pass123!"})
        assert r.status_code == 422


# ── Sensitive Data Not Exposed ────────────────────────────────────────────────
class TestSensitiveDataExposure:
    @pytest.mark.asyncio
    async def test_password_hash_absent_in_me_response(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val={**BASE_USER, "password_hash": hash_password("Pass123!")})
        r = await ac.get("/api/auth/me",
                         headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        body = r.json()
        assert "password_hash" not in body
        assert "password" not in body

    @pytest.mark.asyncio
    async def test_otp_not_in_verify_response(self, ac):
        now = datetime.now(timezone.utc)
        patch_all_db(pending_val={
            "email": "v@t.com", "verification_otp": "999888",
            "otp_created_at": now, "failed_otp_attempts": 0,
            "password_hash": "$2b$12$x", "name": None, "ip_address": "127.0.0.1"},
            users_val=None)
        r = await ac.post("/api/auth/verify-email",
                          json={"email": "v@t.com", "otp": "999888"})
        assert r.status_code == 200
        assert "otp" not in r.json()
        assert "password_hash" not in r.json()
