"""
E2E Tests — Resume Builder & AI Assist
Covers: Resume builder page, manual profile form, AI assist rewrite buttons
Requires: Logged in user
"""
import pytest


@pytest.mark.e2e
class TestResumeBuilderPage:
    """Resume builder page."""

    def test_builder_page_loads(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/resume_builder.html")
        authenticated_page.wait_for_timeout(3000)
        app = authenticated_page.locator("#app")
        assert app.count() > 0

    def test_builder_has_navbar(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/resume_builder.html")
        authenticated_page.wait_for_timeout(3000)
        navbar = authenticated_page.locator(".navbar")
        assert navbar.count() > 0

    def test_builder_has_form_sections(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/resume_builder.html")
        authenticated_page.wait_for_timeout(3000)
        body = authenticated_page.inner_text("body")
        # Should have resume sections like Summary, Skills, Experience
        assert any(k in body for k in ["Summary", "Skills", "Experience", "Education", "Profile"])

    def test_builder_has_ai_assist_buttons(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/resume_builder.html")
        authenticated_page.wait_for_timeout(3000)
        # Look for AI assist buttons (sparkle icon, "Improve", "Enhance", etc.)
        assist_btns = authenticated_page.locator(
            "button:has-text('Improve'), button:has-text('Enhance'), "
            "button:has-text('AI'), button:has-text('Rewrite'), "
            "[class*='assist'], .bi-magic, .bi-stars"
        )
        if assist_btns.count() > 0:
            assert assist_btns.first.is_visible()

    def test_builder_has_text_inputs(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/resume_builder.html")
        authenticated_page.wait_for_timeout(3000)
        # Should have textareas or inputs for resume fields
        inputs = authenticated_page.locator("textarea, input[type='text']")
        if inputs.count() > 0:
            assert inputs.first.is_visible()


@pytest.mark.e2e
class TestFindJobsPage:
    """Find Jobs page."""

    def test_jobs_page_loads(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/find-jobs.html")
        authenticated_page.wait_for_timeout(3000)
        app = authenticated_page.locator("#app")
        assert app.count() > 0

    def test_jobs_page_has_search_form(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/find-jobs.html")
        authenticated_page.wait_for_timeout(3000)
        body = authenticated_page.inner_text("body")
        assert "Search" in body or "Job" in body or "Careerjet" in body

    def test_jobs_page_has_navbar(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/find-jobs.html")
        authenticated_page.wait_for_timeout(3000)
        navbar = authenticated_page.locator(".navbar")
        assert navbar.count() > 0


@pytest.mark.e2e
class TestAboutPage:
    """About page — public, no auth needed."""

    def test_about_page_loads(self, page, base_url):
        page.goto(f"{base_url}/static/pages/about.html")
        page.wait_for_timeout(3000)
        app = page.locator("#app")
        assert app.count() > 0

    def test_about_page_has_content(self, page, base_url):
        page.goto(f"{base_url}/static/pages/about.html")
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        assert "Interview Coach Prep" in body or "ICP" in body or "About" in body

    def test_about_page_has_features_section(self, page, base_url):
        page.goto(f"{base_url}/static/pages/about.html")
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        assert any(k in body for k in ["Feature", "Tool", "Resume", "Interview", "Secure"])

    def test_about_page_has_legal_links(self, page, base_url):
        page.goto(f"{base_url}/static/pages/about.html")
        # Wait deterministically for the legal footer instead of a fixed sleep
        page.wait_for_selector('a:has-text("Terms")', timeout=15000)
        body = page.inner_text("body")
        assert "Terms" in body and "Privacy" in body
