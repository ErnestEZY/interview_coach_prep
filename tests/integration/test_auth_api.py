"""Integration Tests — Authentication API"""
import os, sys, pytest, pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db, make_col

@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

UID = "507f191e810c19729de860ea"


# ── Register ──────────────────────────────────────────────────────────────────
class TestRegister:
    @pytest.mark.asyncio
    async def test_new_email_returns_200(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/register", json={"email": "new@test.com", "password": "Pass123!"})
        assert r.status_code == 200
        assert "otp" in r.json()

    @pytest.mark.asyncio
    async def test_existing_email_returns_400(self, ac):
        patch_all_db(users_val={"email": "exists@test.com"})
        r = await ac.post("/api/auth/register", json={"email": "exists@test.com", "password": "Pass123!"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, ac):
        r = await ac.post("/api/auth/register", json={"email": "bad", "password": "Pass123!"})
        assert r.status_code == 422


# ── Verify Email ──────────────────────────────────────────────────────────────
class TestVerifyEmail:
    def _p(self, otp="123456", mins=0, attempts=0):
        return {"email": "v@t.com", "verification_otp": otp,
                "otp_created_at": datetime.now(timezone.utc) - timedelta(minutes=mins),
                "failed_otp_attempts": attempts,
                "password_hash": "$2b$12$x", "name": None, "ip_address": "127.0.0.1"}

    @pytest.mark.asyncio
    async def test_valid_otp_succeeds(self, ac):
        patch_all_db(pending_val=self._p(), users_val=None)
        r = await ac.post("/api/auth/verify-email", json={"email": "v@t.com", "otp": "123456"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_wrong_otp_returns_400(self, ac):
        patch_all_db(pending_val=self._p(otp="999999"))
        r = await ac.post("/api/auth/verify-email", json={"email": "v@t.com", "otp": "000000"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_expired_otp_returns_400(self, ac):
        patch_all_db(pending_val=self._p(mins=20))
        r = await ac.post("/api/auth/verify-email", json={"email": "v@t.com", "otp": "123456"})
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_no_session_returns_404(self, ac):
        patch_all_db(pending_val=None, users_val=None)
        r = await ac.post("/api/auth/verify-email", json={"email": "x@t.com", "otp": "000000"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_three_failures_deletes_session(self, ac):
        patch_all_db(pending_val=self._p(otp="999999", attempts=2))
        r = await ac.post("/api/auth/verify-email", json={"email": "v@t.com", "otp": "000000"})
        assert r.status_code == 400
        assert "register again" in r.json()["detail"].lower()


# ── Resend OTP ────────────────────────────────────────────────────────────────
class TestResendOtp:
    @pytest.mark.asyncio
    async def test_after_cooldown_returns_200(self, ac):
        old = datetime.now(timezone.utc) - timedelta(seconds=35)
        patch_all_db(pending_val={"email": "r@t.com", "otp_created_at": old})
        r = await ac.post("/api/auth/resend-otp", json={"email": "r@t.com"})
        assert r.status_code == 200
        assert "otp" in r.json()

    @pytest.mark.asyncio
    async def test_within_cooldown_returns_429(self, ac):
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        patch_all_db(pending_val={"email": "r@t.com", "otp_created_at": recent})
        r = await ac.post("/api/auth/resend-otp", json={"email": "r@t.com"})
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_no_session_returns_404(self, ac):
        patch_all_db(pending_val=None)
        r = await ac.post("/api/auth/resend-otp", json={"email": "x@t.com"})
        assert r.status_code == 404


# ── Login ─────────────────────────────────────────────────────────────────────
class TestLogin:
    def _u(self, pw, verified=True, locked=False, attempts=0):
        return {"_id": UID, "email": "u@t.com", "password_hash": pw,
                "role": "user", "is_verified": verified,
                "failed_login_attempts": attempts,
                "lockout_until": (datetime.now(timezone.utc) + timedelta(minutes=5)) if locked else None}

    @pytest.mark.asyncio
    async def test_valid_credentials_returns_token(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val=self._u(hash_password("Pass123!")))
        r = await ac.post("/api/auth/login", data={"username": "u@t.com", "password": "Pass123!"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val=self._u(hash_password("Correct1!")))
        r = await ac.post("/api/auth/login", data={"username": "u@t.com", "password": "Wrong!"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_email_returns_404(self, ac):
        patch_all_db(users_val=None)
        r = await ac.post("/api/auth/login", data={"username": "x@t.com", "password": "Pass123!"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_locked_account_returns_429(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val=self._u(hash_password("Pass123!"), locked=True))
        r = await ac.post("/api/auth/login", data={"username": "u@t.com", "password": "Pass123!"})
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_unverified_returns_403(self, ac):
        from backend.core.security import hash_password
        patch_all_db(users_val=self._u(hash_password("Pass123!"), verified=False))
        r = await ac.post("/api/auth/login", data={"username": "u@t.com", "password": "Pass123!"})
        assert r.status_code == 403
