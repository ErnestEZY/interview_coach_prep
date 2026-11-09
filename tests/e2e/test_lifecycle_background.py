"""App lifecycle: backgrounding, freezing, force-close and relaunch.

Simulates what a user does to their tab or installed app:
  - switching tabs (page visibility hidden/visible),
  - the task queue going away and coming back,
  - OS freezing the page (Chromium web lifecycle state),
  - force-closing mid-request and relaunching (storage_state restore),
  - reload / history navigation preserving the session.

Engine matrix. Freezing the page outright is a CDP command
(``Page.setWebLifecycleState``) with no Firefox or WebKit equivalent, so only
Chromium can be frozen. Everything a freeze must not break — queued work is not
dropped, the page stays interactive, no uncaught errors — is covered on all
three engines by ``test_main_thread_stall_preserves_queued_work``, which stops
the task queue the other engines do allow. The two CDP tests therefore add the
renderer-freeze case on Chromium rather than being the only coverage of it.
"""
import time

import pytest

pytestmark = pytest.mark.e2e

LOGIN = "/static/pages/login.html"
DASHBOARD = "/static/pages/dashboard.html"


def watch_errors(page):
    """Collect uncaught page errors for later assertion."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors


def assert_still_interactive(page, errors, email="thawed@example.com"):
    """The properties every lifecycle test protects, whichever way the page
    was made unavailable."""
    page.fill('input[name="email"]', email)
    assert page.input_value('input[name="email"]') == email, (
        "page stopped accepting input after being backgrounded"
    )
    assert errors == [], f"Uncaught errors while the page was unavailable: {errors}"


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
            # Freezing a page is a CDP capability; Firefox and WebKit expose no
            # equivalent. What a freeze must not break is still covered on every
            # engine by test_main_thread_stall_preserves_queued_work below.
            pytest.skip(
                f"{browser.browser_type.name} has no CDP Page.setWebLifecycleState; "
                "freeze is untestable there"
            )
        context = browser.new_context()
        try:
            page = context.new_page()
            errors = watch_errors(page)
            page.goto(f"{base_url}{LOGIN}")
            page.wait_for_selector("text=Welcome Back")

            cdp = context.new_cdp_session(page)
            cdp.send("Page.enable")
            for _ in range(3):
                cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
                page.wait_for_timeout(300)
                cdp.send("Page.setWebLifecycleState", {"state": "active"})
                page.wait_for_timeout(300)

            assert_still_interactive(page, errors)
        finally:
            context.close()

    def test_main_thread_stall_preserves_queued_work(self, browser, base_url):
        """The engine-neutral half of a freeze: the task queue goes away.

        Blocking the main thread stops timers and rendering the way a frozen
        renderer does, on every engine, without CDP. Two things must hold when
        it resumes: a timer that came due during the stall still runs (it was
        deferred, not dropped), and the page is still interactive.
        """
        context = browser.new_context()
        try:
            page = context.new_page()
            errors = watch_errors(page)
            page.goto(f"{base_url}{LOGIN}")
            page.wait_for_selector("text=Welcome Back")

            page.evaluate(
                """() => {
                  window.__probe = { scheduledAt: performance.now(), firedAt: null };
                  setTimeout(() => { window.__probe.firedAt = performance.now(); },
                             200);
                  const until = performance.now() + 800;
                  while (performance.now() < until) { /* occupy the thread */ }
                }"""
            )
            page.wait_for_function(
                "() => window.__probe && window.__probe.firedAt !== null",
                timeout=10000,
            )
            probe = page.evaluate("() => window.__probe")
            latency = probe["firedAt"] - probe["scheduledAt"]
            assert latency >= 790, (
                f"the 200ms timer fired {latency:.0f}ms after it was set, during "
                f"an 800ms stall — the stall did not actually happen"
            )
            assert latency < 6000, (
                f"the timer took {latency:.0f}ms to fire once the thread was "
                f"free; queued work is not being resumed promptly"
            )

            # The page must also still reach the server, not merely accept input.
            status = page.evaluate(
                "async () => (await fetch('/api/auth/config')).status"
            )
            assert status == 200, f"requests fail after a stall: HTTP {status}"

            assert_still_interactive(page, errors)
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
            # See test_repeated_freeze_thaw_cycles_stay_healthy: freeze and thaw
            # is a CDP capability with no Firefox or WebKit equivalent, and
            # test_main_thread_stall_preserves_queued_work covers the property
            # on those two engines.
            pytest.skip(
                f"{browser.browser_type.name} has no CDP Page.setWebLifecycleState; "
                "freeze is untestable there"
            )
        context = browser.new_context()
        try:
            page = context.new_page()
            errors = watch_errors(page)
            page.goto(f"{base_url}/static/pages/login.html")
            page.wait_for_selector("text=Welcome Back")

            cdp = context.new_cdp_session(page)
            cdp.send("Page.enable")
            cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
            time.sleep(1)
            cdp.send("Page.setWebLifecycleState", {"state": "active"})

            assert page.evaluate("1 + 1") == 2
            assert_still_interactive(page, errors)
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
