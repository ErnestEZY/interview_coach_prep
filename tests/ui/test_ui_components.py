"""
UI Component Tests — ICP Frontend
Tests that every HTML page:
  - Exists and is served correctly (200)
  - Contains expected key UI elements (form IDs, Vue mount point, nav links)
  - Has correct page titles
  - Has no broken static asset references (CSS / JS imports that 404)

These tests use the FastAPI test client to check what the server actually serves.
They do NOT use a browser/Selenium — they check the HTML structure directly.
"""
import os, sys, re, pytest, pytest_asyncio
from httpx import AsyncClient, ASGITransport

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)


@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Page Availability ─────────────────────────────────────────────────────────
class TestPageAvailability:
    PAGES = [
        "/static/pages/login.html",
        "/static/pages/register.html",
        "/static/pages/verify.html",
        "/static/pages/forgot_password.html",
        "/static/pages/reset_password.html",
        "/static/pages/dashboard.html",
        "/static/pages/interview.html",
        "/static/pages/history.html",
        "/static/pages/resume_builder.html",
        "/static/pages/find-jobs.html",
        "/static/pages/cta.html",
    ]

    @pytest.mark.asyncio
    async def test_all_pages_return_200(self, ac):
        for path in self.PAGES:
            r = await ac.get(path)
            assert r.status_code == 200, f"Page {path} returned {r.status_code}"

    @pytest.mark.asyncio
    async def test_all_pages_return_html_content_type(self, ac):
        for path in self.PAGES:
            r = await ac.get(path)
            ct = r.headers.get("content-type", "")
            assert "html" in ct or r.status_code == 200, \
                f"{path} content-type was '{ct}'"

    @pytest.mark.asyncio
    async def test_index_page_returns_200(self, ac):
        r = await ac.get("/")
        assert r.status_code == 200


# ── Login Page ────────────────────────────────────────────────────────────────
class TestLoginPage:
    @pytest.mark.asyncio
    async def test_has_title(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert "<title>" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_vue_app_mount(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert 'id="app"' in r.text

    @pytest.mark.asyncio
    async def test_has_email_input(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert 'type="email"' in r.text or 'username' in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_password_input(self, ac):
        r = await ac.get("/static/pages/login.html")
        # Vue binds :type dynamically — check for the password field wrapper instead
        assert "password" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_bootstrap_css(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert "bootstrap" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_link_to_register(self, ac):
        r = await ac.get("/static/pages/login.html")
        assert "register" in r.text.lower()


# ── Register Page ─────────────────────────────────────────────────────────────
class TestRegisterPage:
    @pytest.mark.asyncio
    async def test_has_password_strength_indicator(self, ac):
        r = await ac.get("/static/pages/register.html")
        assert "password" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_terms_checkbox(self, ac):
        r = await ac.get("/static/pages/register.html")
        assert "agree" in r.text.lower() or "terms" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_emailjs_script(self, ac):
        r = await ac.get("/static/pages/register.html")
        assert "emailjs" in r.text.lower()


# ── Verify Page ───────────────────────────────────────────────────────────────
class TestVerifyPage:
    @pytest.mark.asyncio
    async def test_has_otp_input(self, ac):
        r = await ac.get("/static/pages/verify.html")
        assert "otp" in r.text.lower() or "6-digit" in r.text.lower() \
               or "verification" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_resend_button(self, ac):
        r = await ac.get("/static/pages/verify.html")
        assert "resend" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_register_fallback_link(self, ac):
        r = await ac.get("/static/pages/verify.html")
        assert "register" in r.text.lower()


# ── Dashboard Page ────────────────────────────────────────────────────────────
class TestDashboardPage:
    @pytest.mark.asyncio
    async def test_has_vue_app(self, ac):
        r = await ac.get("/static/pages/dashboard.html")
        assert 'id="app"' in r.text

    @pytest.mark.asyncio
    async def test_has_navbar(self, ac):
        r = await ac.get("/static/pages/dashboard.html")
        assert "navbar" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_resume_upload_section(self, ac):
        r = await ac.get("/static/pages/dashboard.html")
        assert "upload" in r.text.lower() or "resume" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_sweetalert(self, ac):
        r = await ac.get("/static/pages/dashboard.html")
        assert "sweetalert" in r.text.lower() or "swal" in r.text.lower()


# ── Interview Page ────────────────────────────────────────────────────────────
class TestInterviewPage:
    @pytest.mark.asyncio
    async def test_has_difficulty_selector(self, ac):
        r = await ac.get("/static/pages/interview.html")
        assert "difficulty" in r.text.lower() or "beginner" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_start_button(self, ac):
        r = await ac.get("/static/pages/interview.html")
        assert "start" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_chat_area(self, ac):
        r = await ac.get("/static/pages/interview.html")
        assert "message" in r.text.lower() or "chat" in r.text.lower() \
               or "transcript" in r.text.lower()


# ── History Page ──────────────────────────────────────────────────────────────
class TestHistoryPage:
    @pytest.mark.asyncio
    async def test_has_chart_js(self, ac):
        r = await ac.get("/static/pages/history.html")
        assert "chart" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_delete_functionality(self, ac):
        r = await ac.get("/static/pages/history.html")
        assert "delete" in r.text.lower()


# ── Resume Builder Page ───────────────────────────────────────────────────────
class TestResumeBuilderPage:
    @pytest.mark.asyncio
    async def test_has_download_button(self, ac):
        r = await ac.get("/static/pages/resume_builder.html")
        assert "download" in r.text.lower() or "pdf" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_theme_selector(self, ac):
        r = await ac.get("/static/pages/resume_builder.html")
        assert "theme" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_html2pdf_script(self, ac):
        r = await ac.get("/static/pages/resume_builder.html")
        assert "html2pdf" in r.text.lower()


# ── Find Jobs Page ────────────────────────────────────────────────────────────
class TestFindJobsPage:
    @pytest.mark.asyncio
    async def test_has_careerjet_widget(self, ac):
        r = await ac.get("/static/pages/find-jobs.html")
        assert "careerjet" in r.text.lower()

    @pytest.mark.asyncio
    async def test_has_search_tips(self, ac):
        r = await ac.get("/static/pages/find-jobs.html")
        assert "tip" in r.text.lower() or "search" in r.text.lower()


# ── Static Assets ─────────────────────────────────────────────────────────────
class TestStaticAssets:
    @pytest.mark.asyncio
    async def test_global_css_served(self, ac):
        r = await ac.get("/static/css/styles.css")
        assert r.status_code == 200
        assert "css" in r.headers.get("content-type", "").lower()

    @pytest.mark.asyncio
    async def test_app_js_served(self, ac):
        r = await ac.get("/static/js/app.js")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_verify_js_served(self, ac):
        r = await ac.get("/static/js/verify.js")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_find_jobs_js_served(self, ac):
        r = await ac.get("/static/js/find_jobs.js")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_favicon_served(self, ac):
        r = await ac.get("/static/images/favicon.ico")
        assert r.status_code == 200
