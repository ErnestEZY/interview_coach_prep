"""
E2E Tests — Error State Handling
Covers: Progress bar error display, AI rate limit error, timeout handling
Tests that the frontend handles backend errors gracefully
"""
import pytest


DASHBOARD = "/static/pages/dashboard.html"


@pytest.mark.e2e
class TestProgressBarErrorState:
    """The analysis overlay exists only while an analysis runs, and its failure
    state is the thing that tells the user to retry.

    Each test drives the component data instead of waiting for a real analysis:
    the overlay is behind v-if="showAnalysisProgress", so asserting on its
    markup at rest was asserting on a document that did not contain it.
    """

    def test_overlay_absent_until_progress_starts(
        self, authenticated_page, base_url, drive_vue
    ):
        page = authenticated_page
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")
        assert page.locator(".analysis-progress-overlay").count() == 0, (
            "The overlay is in the DOM before an analysis has started"
        )

        assert drive_vue(
            page, showAnalysisProgress=True, analysisStatus="Reading your resume"
        ), "No Vue instance on #app — the dashboard did not mount"

        overlay = page.locator(".analysis-progress-overlay")
        overlay.wait_for(state="visible")
        assert overlay.get_attribute("role") == "dialog"
        assert overlay.get_attribute("aria-modal") == "true"
        body = overlay.inner_text()
        assert "Resume Analysis" in body
        assert "Reading your resume" in body

    def test_progress_bar_reports_width_and_aria(
        self, authenticated_page, base_url, drive_vue
    ):
        """A screen reader follows aria-valuenow; the eye follows the width."""
        page = authenticated_page
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")
        assert drive_vue(page, showAnalysisProgress=True, analysisProgress=42)

        bar = page.locator(".analysis-progress-container .progress-bar")
        bar.wait_for(state="visible")
        assert bar.get_attribute("aria-valuenow") == "42"
        assert "42%" in (bar.get_attribute("style") or "")
        assert "42%" in page.locator(".analysis-progress-card").inner_text()

    def test_failure_switches_overlay_to_error_state(
        self, authenticated_page, base_url, drive_vue
    ):
        """stopAnalysisProgress(false) holds the failure on screen for 800 ms,
        so the whole state is read in one round trip rather than in a sequence
        of lookups that could straddle the moment it clears itself."""
        page = authenticated_page
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")
        assert drive_vue(
            page, showAnalysisProgress=True, analysisProgress=60, analysisStatus="Analysing"
        )

        snapshot = page.evaluate(
            """async () => {
                 const host = document.querySelector('#app');
                 const app = host.__vue_app__;
                 const instance = (app && app._instance) || (host._vnode && host._vnode.component);
                 const vm = instance.proxy;
                 vm.stopAnalysisProgress(false);
                 // Vue applies the change on the next tick; sampling before it
                 // reads the previous render, not the state just entered.
                 await vm.$nextTick();
                 const card = document.querySelector('.analysis-progress-card');
                 const bar = document.querySelector('.analysis-progress-container .progress-bar');
                 return {
                   text: card ? card.innerText : '',
                   barClass: bar ? bar.className : '',
                   spinner: document.querySelectorAll('.analysis-progress-card .spinner-grow').length,
                   errorIcon: document.querySelectorAll('.analysis-progress-card .bi-x-circle-fill').length,
                 };
             }"""
        )
        assert "Analysis Failed" in snapshot["text"]
        assert "Please try again in a moment." in snapshot["text"]
        assert "bg-danger" in snapshot["barClass"]
        assert "bg-primary" not in snapshot["barClass"]
        assert snapshot["spinner"] == 0, "The spinner still suggests work is happening"
        assert snapshot["errorIcon"] == 1

        # It clears itself rather than leaving a dead overlay on the page.
        page.wait_for_function(
            "() => !document.querySelector('.analysis-progress-overlay')", timeout=5000
        )


@pytest.mark.e2e
class TestAIErrorDisplay:
    """Test that AI errors are shown to user via SweetAlert."""

    def test_sweetalert_loaded_on_dashboard(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/dashboard.html")
        authenticated_page.wait_for_timeout(3000)
        # SweetAlert2 should be loaded
        swal = authenticated_page.evaluate("typeof Swal !== 'undefined'")
        assert swal is True

    def test_sweetalert_loaded_on_interview(self, page, base_url):
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        if "login.html" in page.url:
            pytest.skip("Not authenticated")
        swal = page.evaluate("typeof Swal !== 'undefined'")
        assert swal is True

    def test_sweetalert_loaded_on_login(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        swal = page.evaluate("typeof Swal !== 'undefined'")
        assert swal is True


@pytest.mark.e2e
class TestApiErrorHandling:
    """Test that API errors are handled gracefully."""

    def test_interview_start_error_shows_alert(self, authenticated_page, base_url):
        authenticated_page.goto(f"{base_url}/static/pages/interview.html")
        authenticated_page.wait_for_timeout(3000)
        # If interview start fails (429/500), error should be shown
        # Smoke test — verifies SweetAlert is available for error display
        swal = authenticated_page.evaluate("typeof Swal !== 'undefined'")
        assert swal is True


@pytest.mark.e2e
class TestOfflineState:
    """Test offline/network error handling."""

    def test_app_js_loaded(self, page, base_url):
        """app.min.js should be loaded on all pages."""
        for page_path in ["/static/pages/login.html", "/static/pages/register.html"]:
            page.goto(f"{base_url}{page_path}")
            page.wait_for_timeout(2000)
            icp_state = page.evaluate("typeof window.icp !== 'undefined'")
            assert icp_state is True, f"window.icp not defined on {page_path}"

    def test_axios_loaded(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        axios_loaded = page.evaluate("typeof axios !== 'undefined'")
        assert axios_loaded is True

    def test_vue_loaded(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        vue_loaded = page.evaluate("typeof Vue !== 'undefined'")
        assert vue_loaded is True
