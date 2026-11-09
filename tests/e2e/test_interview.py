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

    def test_start_button_exists(self, authenticated_page, base_url):
        """An authenticated visitor must get the real setup screen, not a
        bounce: the previous version skipped itself whenever the button was
        missing, which is the failure mode it was meant to catch."""
        page = authenticated_page
        page.goto(f"{base_url}/static/pages/interview.html")
        btn = page.locator("button:has-text('Start Interview')")
        assert btn.count() >= 1, "No Start Interview button on the setup screen"
        assert btn.first.is_visible()

    def test_question_limit_selector_exists(self, authenticated_page, base_url):
        """The other half of the setup screen: how many questions this session
        runs for. The job title this test used to look for is entered on the
        dashboard (asserted in test_resume.py) — there is no such field here,
        so the old check could never fail."""
        page = authenticated_page
        page.goto(f"{base_url}/static/pages/interview.html")
        select = page.locator("select.question-limit-select")
        assert select.count() == 1, "No question-count selector on the setup screen"
        assert select.is_visible()
        assert select.locator("option").count() > 0

    def test_difficulty_selector_exists(self, authenticated_page, base_url):
        """The setup screen must offer exactly the three documented levels.

        This page redirects anonymous visitors, so the assertion runs on a
        session that stays put; the previous version skipped itself when the
        control was missing and asserted True when it was not.
        """
        page = authenticated_page
        page.goto(f"{base_url}/static/pages/interview.html")
        select = page.locator("select.difficulty-select")
        assert select.count() == 1, "No difficulty selector on the interview setup screen"
        assert select.is_visible()
        assert select.locator("option").all_inner_texts() == [
            "Beginner",
            "Intermediate",
            "Advanced",
        ]


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
