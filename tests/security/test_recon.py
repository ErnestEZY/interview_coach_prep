"""Reconnaissance posture — what an unauthenticated attacker can learn.

Covers file disclosure probes, directory listing, stack traces, CORS
permissiveness, cacheability of auth pages, version banners and how much of
the admin surface is advertised. Complements test_security_api.py (auth
bypass, lockout, injection) with an outside-in attacker view.

Run: pytest tests/security/test_recon.py -v --tb=short
"""
import json
import os
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db  # noqa: E402

UID = "507f191e810c19729de860ea"
SECRET_MARKERS = (
    "OPENAI_API_KEY",
    "MISTRAL_API_KEY",
    "MONGO_URI",
    "JWT_SECRET",
    "EMAILJS_PRIVATE",
    "-----BEGIN",
    "[core]",
    "repositoryformatversion",
)


@pytest_asyncio.fixture
async def ac():
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestFileDisclosure:
    @pytest.mark.parametrize(
        "path",
        [
            "/.env",
            "/.env.example",
            "/.git/config",
            "/.git/HEAD",
            "/backend/main.py",
            "/backend/core/config.py",
            "/requirements.txt",
            "/Dockerfile",
            "/start.sh",
            "/venv/pyvenv.cfg",
        ],
    )
    @pytest.mark.asyncio
    async def test_recon_probes_do_not_leak_files(self, ac, path):
        r = await ac.get(path)
        body = r.text
        for marker in SECRET_MARKERS:
            assert marker not in body, f"{path} leaked {marker!r}"
        # Either a clean 404, or (at worst) the SPA shell — never the raw file.
        if r.status_code == 200:
            assert "text/html" in r.headers.get("content-type", ""), (
                f"{path} was served as {r.headers.get('content-type')}"
            )
        else:
            assert r.status_code in (403, 404), f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("path", ["/static/", "/static/js/", "/static/pages/"])
    @pytest.mark.asyncio
    async def test_no_directory_listing(self, ac, path):
        r = await ac.get(path)
        assert r.status_code in (403, 404), f"{path} -> {r.status_code}"
        lowered = r.text.lower()
        assert "index of" not in lowered
        assert "directory listing" not in lowered


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_malformed_json_has_no_traceback(self, ac):
        r = await ac.post(
            "/api/auth/login",
            content=b'{"email": ',
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code in (400, 422)
        lowered = r.text.lower()
        assert "traceback" not in lowered
        assert 'file "' not in lowered
        assert "site-packages" not in lowered

    @pytest.mark.asyncio
    async def test_unknown_api_route_returns_json_404(self, ac):
        r = await ac.get("/api/definitely-not-a-route")
        assert r.status_code == 404
        assert "detail" in r.json()

    @pytest.mark.asyncio
    async def test_sql_injection_probe_is_not_executed(self, ac):
        # Earlier suites mutate module-level collection bindings; pin the lookup
        # to "no such account" so the assertion is order-independent.
        patch_all_db(users_val=None)
        r = await ac.get("/api/auth/me", params={"id": "' OR 1=1 --"})
        assert r.status_code == 401
        r2 = await ac.post(
            "/api/auth/login",
            data={"username": "' OR '1'='1", "password": "' OR '1'='1"},
        )
        # The app answers unknown accounts with 404 "Email not found"; the
        # injection string must never be treated as SQL (i.e. never 200).
        assert r2.status_code in (400, 401, 404, 422, 429)
        assert r2.status_code != 500


class TestCorsPosture:
    @pytest.mark.asyncio
    async def test_untrusted_origin_is_not_approved(self, ac):
        r = await ac.get("/api/auth/config", headers={"Origin": "https://evil.example"})
        assert r.status_code == 200
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}

    @pytest.mark.asyncio
    async def test_glob_lookalike_origin_is_not_approved(self, ac):
        """allow_origins uses exact strings: *.onrender.com must not glob-match."""
        r = await ac.get(
            "/api/auth/config", headers={"Origin": "https://evil.onrender.com"}
        )
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}

    @pytest.mark.asyncio
    async def test_configured_origin_is_echoed_with_credentials(self, ac):
        origin = "http://localhost:8000"
        r = await ac.get("/api/auth/config", headers={"Origin": origin})
        assert r.headers.get("access-control-allow-origin") == origin
        assert r.headers.get("access-control-allow-credentials") == "true"

    @pytest.mark.asyncio
    async def test_untrusted_preflight_is_rejected(self, ac):
        r = await ac.options(
            "/api/auth/login",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


class TestHeaderHygiene:
    @pytest.mark.asyncio
    async def test_auth_pages_are_not_cacheable(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert r.status_code == 200
        cache_control = r.headers.get("cache-control", "").lower()
        assert "no-store" in cache_control, cache_control

    @pytest.mark.asyncio
    async def test_server_banner_has_no_version(self, ac):
        r = await ac.get("/api/auth/config")
        server = r.headers.get("server", "")
        if server:
            assert "/" not in server, f"Version banner exposed: {server}"

    @pytest.mark.asyncio
    async def test_no_debug_headers_leak_internals(self, ac):
        r = await ac.get("/api/auth/config")
        for header in ("x-powered-by", "x-aspnet-version", "x-debug-token"):
            assert header not in {k.lower() for k in r.headers}


class TestAdminSurface:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/admin/resumes",
            "/api/admin/metrics",
        ],
    )
    @pytest.mark.asyncio
    async def test_admin_apis_require_authentication(self, ac, path):
        r = await ac.get(path)
        assert r.status_code in (401, 403), f"{path} -> {r.status_code}"

    @pytest.mark.asyncio
    async def test_admin_api_rejects_non_admin_user(self, ac):
        patch_all_db(users_val={
            "_id": UID, "email": "u@t.com", "role": "user", "is_verified": True,
            "has_analyzed": True, "daily_resume_count": 0,
            "daily_interview_count": 0, "daily_question_count": 0,
            "daily_reset_at": None, "failed_login_attempts": 0,
            "lockout_until": None,
        })
        headers = {"Authorization": f"Bearer {make_jwt(UID, role='user')}"}
        for path in ("/api/admin/resumes", "/api/admin/metrics"):
            r = await ac.get(path, headers=headers)
            assert r.status_code in (401, 403), f"{path} -> {r.status_code}"

    @pytest.mark.parametrize(
        "path",
        ["/", "/static/pages/login.html", "/static/pages/dashboard.html"],
    )
    @pytest.mark.asyncio
    async def test_public_pages_do_not_advertise_admin_entry(self, ac, path):
        r = await ac.get(path)
        assert r.status_code == 200
        assert "x7k2mP9a" not in r.text
        assert "icp-admin-hub" not in r.text

    @pytest.mark.asyncio
    async def test_openapi_schema_hides_obscured_admin_portal(self, ac):
        r = await ac.get("/openapi.json")
        if r.status_code != 200:
            return  # docs disabled is an even stronger posture
        schema = json.dumps(r.json())
        assert "/icp/admin" not in schema
        assert "x7k2mP9a" not in schema

    @pytest.mark.asyncio
    async def test_robots_txt_does_not_disclose_admin_paths(self, ac):
        r = await ac.get("/robots.txt")
        assert r.status_code == 200
        lowered = r.text.lower()
        assert "icp-admin" not in lowered
        assert "/icp/admin" not in lowered
