"""
E2E Tests — Network Resilience & Session Lifecycle
Covers:
  - Network loss: full offline mode (CDP emulation), total API outage via
    route aborts, injected 5xx and 429 responses — pages must degrade
    gracefully, never crash or blank out.
  - Backgrounding / force-close (web equivalents): session persistence across
    a full context recreation (app relaunch), reload preserving auth, and
    back/forward navigation stability.
"""
import pytest


def _authed_context(browser, token, **kwargs):
    """Fresh browser context with the E2E user's JWT pre-seeded."""
    context = browser.new_context(**kwargs)
    if token:
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{token}'); }} catch (e) {{ }}"
        )
    return context


@pytest.mark.e2e
class TestOfflineMode:
    """Real network loss — offline emulation and total API outage."""

    def test_full_offline_navigation_fails_then_recovers(self, browser, base_url):
        context = browser.new_context()
        page = context.new_page()
        context.set_offline(True)
        raised = False
        try:
            page.goto(f"{base_url}/static/pages/login.html", timeout=15000)
        except Exception as exc:
            raised = True
            # Engine-specific offline error surfaces (Chromium: net::ERR,
            # Firefox: NS_ERROR, WebKit: "encountered an internal error")
            assert (
                "net::ERR" in str(exc)
                or "NS_ERROR" in str(exc)
                or "internal error" in str(exc)
                or "Timeout" in str(exc)
            ), f"Unexpected offline error: {exc}"
        assert raised, "Navigation unexpectedly succeeded while offline"
        # Back online — the app recovers without any user intervention
        context.set_offline(False)
        page.goto(f"{base_url}/static/pages/login.html")
        assert page.locator("#app").count() > 0
        context.close()

    def test_total_api_outage_still_renders_dashboard_shell(self, browser, base_url, test_user_token):
        """With every /api route dead the Vue shell must still mount with
        the upload UI present — never a blank page or a crash."""
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.route("**/api/**", lambda route: route.abort())
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        # Whichever graceful outcome the app chooses (stay on dashboard or
        # bounce to login), it must land on a rendered app page — not crash.
        assert page.locator("#app").count() > 0
        assert any(p in page.url for p in ("dashboard.html", "login.html")), (
            f"Unexpected landing page during API outage: {page.url}"
        )
        context.close()

    def test_interview_shell_survives_api_outage(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.route("**/api/**", lambda route: route.abort())
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        # The interview page soft-gates: shell and Start control must exist
        assert page.locator("#app").count() > 0
        assert page.locator("button:has-text('Start Interview')").count() > 0
        context.close()


@pytest.mark.e2e
class TestApiFailureInjection:
    """Server-side failure responses injected via route interception."""

    def test_auth_me_500_does_not_crash_dashboard(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.route(
            "**/api/auth/me",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body='{"detail": "Internal Server Error"}',
            ),
        )
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        assert page.locator("#app").count() > 0
        assert any(p in page.url for p in ("dashboard.html", "login.html"))
        context.close()

    def test_rate_limit_429_on_limits_endpoint_is_handled(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.route(
            "**/api/*/limits",
            lambda route: route.fulfill(
                status=429,
                content_type="application/json",
                body='{"detail": "Rate limit exceeded"}',
            ),
        )
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        assert page.locator("#app").count() > 0
        assert "login.html" not in page.url
        context.close()


@pytest.mark.e2e
class TestSessionLifecycle:
    """Backgrounding / force-close web equivalents."""

    def test_session_persists_across_app_relaunch(self, browser, base_url, test_user_token):
        """Close the whole context (force-close) and relaunch from the
        persisted storage state — the session must survive."""
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        assert "dashboard.html" in page.url
        state = context.storage_state()
        context.close()

        context2 = browser.new_context(storage_state=state)
        page2 = context2.new_page()
        page2.goto(f"{base_url}/static/pages/dashboard.html")
        page2.wait_for_timeout(3000)
        assert "login.html" not in page2.url, "Session lost after relaunch"
        assert page2.locator("#app").count() > 0
        context2.close()

    def test_reload_preserves_authentication(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        page.reload()
        page.wait_for_timeout(3000)
        assert "login.html" not in page.url, "Reload bounced the user to login"
        assert page.locator("#app").count() > 0
        context.close()

    def test_back_forward_navigation_does_not_break_session(self, browser, base_url, test_user_token):
        """The app installs popstate guards — history traversal must leave
        the session on a valid, rendered app page."""
        if not test_user_token:
            pytest.skip("No test user token available")
        context = _authed_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_timeout(3000)
        page.go_back()
        page.wait_for_timeout(2000)
        page.go_forward()
        page.wait_for_timeout(3000)
        assert page.locator("#app").count() > 0
        assert "icp-admin" not in page.url
        context.close()
