"""App lifecycle: backgrounding, freezing, force-close and relaunch.

Simulates what a user does to their tab or installed app:
  - switching tabs (page visibility hidden/visible),
  - OS freezing the page (Chromium web lifecycle state),
  - force-closing mid-request and relaunching (storage_state restore),
  - reload / history navigation preserving the session.
"""
import time

import pytest

pytestmark = pytest.mark.e2e

LOGIN = "/static/pages/login.html"
DASHBOARD = "/static/pages/dashboard.html"


@pytest.fixture
def authed_context(browser, base_url, test_user_token):
    """Authenticated context with a token seeded before any page script."""
    if not test_user_token:
        pytest.skip("No test user token available")
    context = browser.new_context()
    context.add_init_script(
        f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
    )
    yield context
    context.close()


class TestBackgrounding:
    def test_tab_switch_preserves_page_state(self, browser, base_url):
        """Switching tabs and coming back must keep entered state and a live,
        interactive page (headless engines never report visibility changes)."""
        context = browser.new_context()
        try:
            tab_a = context.new_page()
            tab_a.goto(f"{base_url}{LOGIN}")
            tab_a.wait_for_selector("text=Welcome Back")
            tab_a.fill('input[name="email"]', "backgrounded@example.com")

            tab_b = context.new_page()
            tab_b.goto(f"{base_url}/static/pages/about.html")
            tab_b.wait_for_selector("text=Career Launchpad")
            tab_b.bring_to_front()
            tab_b.wait_for_timeout(1000)

            tab_a.bring_to_front()
            assert tab_a.input_value('input[name="email"]') == "backgrounded@example.com"
            # Page JS is still alive: the password toggle flips the input type
            tab_a.locator("button.password-toggle-btn").click()
            assert tab_a.get_attribute('input[name="password"]', "type") == "text"
        finally:
            context.close()

    def test_repeated_freeze_thaw_cycles_stay_healthy(self, browser, base_url):
        """Repeated OS background/wake cycles must not corrupt the page:
        JS stays alive and the UI remains interactive after each wake."""
        if browser.browser_type.name != "chromium":
            pytest.skip("Page lifecycle freezing is Chromium-only via CDP")
        context = browser.new_context()
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{base_url}{LOGIN}")
            page.wait_for_selector("text=Welcome Back")

            cdp = context.new_cdp_session(page)
            cdp.send("Page.enable")
            for _ in range(3):
                cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
                page.wait_for_timeout(300)
                cdp.send("Page.setWebLifecycleState", {"state": "active"})
                page.wait_for_timeout(300)

            page.fill('input[name="email"]', "thawed@example.com")
            assert page.input_value('input[name="email"]') == "thawed@example.com"
            assert errors == [], f"Uncaught errors across freeze cycles: {errors}"
        finally:
            context.close()

    def test_backgrounded_tab_keeps_session(self, authed_context, base_url):
        page = authed_context.new_page()
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")

        other = authed_context.new_page()
        other.goto(f"{base_url}/")
        other.bring_to_front()
        other.wait_for_timeout(2000)
        page.bring_to_front()

        page.reload()
        page.wait_for_selector("#app", state="visible")
        assert "dashboard.html" in page.url

    def test_frozen_page_resumes_without_crash(self, browser, base_url):
        if browser.browser_type.name != "chromium":
            pytest.skip("Page lifecycle freezing is Chromium-only via CDP")
        context = browser.new_context()
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{base_url}/static/pages/login.html")
            page.wait_for_selector("text=Welcome Back")

            cdp = context.new_cdp_session(page)
            cdp.send("Page.enable")
            cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
            time.sleep(1)
            cdp.send("Page.setWebLifecycleState", {"state": "active"})

            assert page.evaluate("1 + 1") == 2
            page.fill('input[name="email"]', "thawed@example.com")
            assert page.input_value('input[name="email"]') == "thawed@example.com"
            assert errors == []
        finally:
            context.close()


class TestForceCloseAndRelaunch:
    def test_relaunch_restores_authenticated_session(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")

        first = browser.new_context()
        first.add_init_script(
            f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
        )
        page = first.new_page()
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")
        state = first.storage_state()
        first.close()  # force-close the app

        relaunched = browser.new_context(storage_state=state)
        try:
            page2 = relaunched.new_page()
            page2.goto(f"{base_url}{DASHBOARD}")
            page2.wait_for_selector("#app", state="visible")
            assert "dashboard.html" in page2.url, "Session lost after relaunch"
        finally:
            relaunched.close()

    def test_relaunch_without_state_returns_to_login(self, browser, base_url):
        fresh = browser.new_context()
        try:
            page = fresh.new_page()
            page.goto(f"{base_url}{DASHBOARD}")
            page.wait_for_url("**/login.html", timeout=20000)
        finally:
            fresh.close()

    def test_force_close_mid_request_keeps_server_healthy(self, browser, base_url):
        context = browser.new_context()
        page = context.new_page()

        def hang(route):
            try:
                time.sleep(3)
                route.fulfill(status=401, content_type="application/json",
                              body='{"detail": "Invalid credentials"}')
            except Exception:
                pass  # context closed underneath the handler

        page.route("**/api/auth/login", hang)
        page.goto(f"{base_url}{LOGIN}")
        page.wait_for_selector("text=Welcome Back")
        page.fill('input[name="email"]', "forceclose@example.com")
        page.fill('input[name="password"]', "ForceClose1!")
        page.locator('button[type="submit"]').click(no_wait_after=True)
        page.wait_for_timeout(300)
        context.close()  # kill the app while the login request is pending

        probe = browser.new_context()
        try:
            response = probe.new_page().request.get(f"{base_url}/api/auth/config")
            assert response.status == 200
        finally:
            probe.close()


class TestSessionContinuity:
    def test_reload_and_reenavigation_keep_session(self, authed_context, base_url):
        page = authed_context.new_page()
        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")

        page.reload()
        page.wait_for_selector("#app", state="visible")
        assert "dashboard.html" in page.url

        page.goto(f"{base_url}/static/pages/about.html")
        page.wait_for_selector("text=Career Launchpad")
        page.go_back()  # app.js history trap keeps public pages in place
        page.wait_for_timeout(800)
        assert "about.html" in page.url

        page.goto(f"{base_url}{DASHBOARD}")
        page.wait_for_selector("#app", state="visible")
        assert "dashboard.html" in page.url, "Session lost after navigation churn"
