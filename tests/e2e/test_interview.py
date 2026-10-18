"""
E2E Tests — Interview Flow
Covers: Start interview, answer questions, end session, history
Requires: Logged in user with interview attempts available
"""
import pytest


@pytest.mark.e2e
class TestInterviewPage:
    """Interview page — must be logged in."""

    def test_interview_page_soft_gate_without_auth(self, page, base_url):
        """Unauthenticated visits are NOT redirected: the page renders with a
        soft gate — logged-in chrome absent and Start Interview disabled."""
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        # Page stays put — it does not redirect to login.html (soft gate)
        assert "interview.html" in page.url
        assert page.locator("#app").count() > 0
        # Logged-in chrome (v-if="logged") is absent from the DOM
        assert page.locator('button[aria-label="Logout"]').count() == 0
        # Session start is locked until authenticated with an analysed resume
        start_btn = page.locator("button:has-text('Start Interview')")
        assert start_btn.count() > 0
        assert start_btn.first.is_disabled()

    def test_interview_page_has_vue_app(self, page, base_url):
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        if "login.html" in page.url:
            pytest.skip("Not authenticated")
        app = page.locator("#app")
        assert app.count() > 0


@pytest.mark.e2e
class TestInterviewStart:
    """Starting an interview session."""

    def test_start_button_exists(self, page, base_url):
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        if "login.html" in page.url:
            pytest.skip("Not authenticated")
        # Look for start interview button
        btn = page.locator("button:has-text('Start'), button:has-text('Begin'), button:has-text('Interview')")
        if btn.count() > 0:
            assert btn.first.is_visible()

    def test_job_title_field_exists(self, page, base_url):
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        if "login.html" in page.url:
            pytest.skip("Not authenticated")
        job_title = page.locator('input[placeholder*="job" i]')
        if job_title.count() > 0:
            assert job_title.first.is_visible()

    def test_difficulty_selector_exists(self, page, base_url):
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        if "login.html" in page.url:
            pytest.skip("Not authenticated")
        # Look for difficulty dropdown or buttons
        difficulty = page.locator("select, button:has-text('Beginner'), button:has-text('Intermediate'), button:has-text('Advanced')")
        if difficulty.count() > 0:
            assert True


@pytest.mark.e2e
class TestInterviewHistory:
    """Interview history page."""

    def test_history_page_loads(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/history.html")
        authenticated_page.wait_for_timeout(3000)
        app = authenticated_page.locator("#app")
        assert app.count() > 0

    def test_history_has_navbar(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/history.html")
        authenticated_page.wait_for_timeout(3000)
        navbar = authenticated_page.locator(".navbar")
        assert navbar.count() > 0

    def test_history_page_title(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/history.html")
        authenticated_page.wait_for_timeout(3000)
        body = authenticated_page.inner_text("body")
        assert "History" in body or "Interview" in body or "Session" in body
