"""Smoke Tests — ICP Application startup and route reachability."""
import os, sys, pytest, pytest_asyncio
from httpx import AsyncClient, ASGITransport

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestApplicationStartup:
    @pytest.mark.asyncio
    async def test_favicon_returns_204(self, ac):
        assert (await ac.get("/favicon.ico")).status_code == 204

    @pytest.mark.asyncio
    async def test_startup_id_reachable(self, ac):
        r = await ac.get("/api/meta/startup_id")
        assert r.status_code == 200
        assert "startup_id" in r.json()

    @pytest.mark.asyncio
    async def test_root_serves_html(self, ac):
        r = await ac.get("/")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()

    @pytest.mark.asyncio
    async def test_find_jobs_route_reachable(self, ac):
        r = await ac.get("/find-jobs/")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_config_returns_200(self, ac):
        r = await ac.get("/api/auth/config")
        assert r.status_code == 200


class TestApiRoutesSmokeCheck:
    @pytest.mark.asyncio
    async def test_login_endpoint_exists(self, ac):
        # empty body → 422 Unprocessable, not 404
        assert (await ac.post("/api/auth/login", data={})).status_code == 422

    @pytest.mark.asyncio
    async def test_register_endpoint_exists(self, ac):
        assert (await ac.post("/api/auth/register", json={})).status_code == 422

    @pytest.mark.asyncio
    async def test_resume_upload_requires_auth(self, ac):
        assert (await ac.post("/api/resume/upload")).status_code == 401

    @pytest.mark.asyncio
    async def test_interview_start_requires_auth(self, ac):
        assert (await ac.post("/api/interview/start")).status_code == 401

    @pytest.mark.asyncio
    async def test_admin_resumes_requires_auth(self, ac):
        assert (await ac.get("/api/admin/resumes")).status_code == 401

    @pytest.mark.asyncio
    async def test_jobs_endpoint_requires_keywords(self, ac):
        # no keywords param → 422, not 404
        assert (await ac.get("/api/jobs")).status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_api_path_not_500(self, ac):
        r = await ac.get("/api/nonexistent/route")
        assert r.status_code != 500

    @pytest.mark.asyncio
    async def test_download_endpoints_not_500(self, ac):
        r = await ac.get("/downloads/apk/app-release.apk")
        assert r.status_code in (200, 404)   # 200 if binary present, 404 if not
        assert r.status_code != 500
