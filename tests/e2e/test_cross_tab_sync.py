"""Cross-tab synchronisation: shared storage, logout propagation, shared SW.

A user commonly keeps ICP open in several tabs (or the installed app plus a
browser tab). This suite verifies the state they share, what propagates
instantly, what only takes effect after a reload, and that the service worker
is a single shared instance per origin.
"""
import pytest

pytestmark = pytest.mark.e2e

ABOUT = "/static/pages/about.html"
DASHBOARD = "/static/pages/dashboard.html"


def _seed_token(context, base_url, token):
    """Write the token through a real page so the origin's storage is used."""
    seed = context.new_page()
    seed.goto(f"{base_url}{ABOUT}")
    seed.wait_for_selector("text=Career Launchpad")
    seed.evaluate("t => localStorage.setItem('token', t)", token)
    seed.close()


class TestSharedStorage:
    def test_localstorage_changes_propagate_between_tabs(self, browser, base_url):
        context = browser.new_context()
        try:
            tab_a = context.new_page()
            tab_a.goto(f"{base_url}{ABOUT}")
            tab_a.wait_for_selector("text=Career Launchpad")

            tab_b = context.new_page()
            tab_b.goto(f"{base_url}{ABOUT}")
            tab_b.wait_for_selector("text=Career Launchpad")

            tab_a.evaluate("() => localStorage.setItem('cross_tab_probe', 'from-a')")
            assert tab_b.evaluate("() => localStorage.getItem('cross_tab_probe')") == "from-a"

            tab_a.evaluate("() => localStorage.removeItem('cross_tab_probe')")
            assert tab_b.evaluate("() => localStorage.getItem('cross_tab_probe')") is None
        finally:
            context.close()

    def test_sessionstorage_is_isolated_per_tab(self, browser, base_url):
        """sessionStorage must not leak across tabs — a tab-scoped marker in
        one tab cannot make another tab believe it just logged in."""
        context = browser.new_context()
        try:
            tab_a = context.new_page()
            tab_a.goto(f"{base_url}{ABOUT}")
            tab_a.wait_for_selector("text=Career Launchpad")

            tab_b = context.new_page()
            tab_b.goto(f"{base_url}{ABOUT}")
            tab_b.wait_for_selector("text=Career Launchpad")

            tab_a.evaluate("() => sessionStorage.setItem('icp_just_logged_in', '1')")
            assert tab_b.evaluate("() => sessionStorage.getItem('icp_just_logged_in')") is None
        finally:
            context.close()


class TestLogoutPropagation:
    def test_logout_in_one_tab_forces_login_on_reload_in_another(
        self, browser, base_url, test_user_token
    ):
        if not test_user_token:
            pytest.skip("No test user token available")

        context = browser.new_context()
        try:
            _seed_token(context, base_url, test_user_token)

            tab_a = context.new_page()
            tab_a.goto(f"{base_url}{DASHBOARD}")
            tab_a.wait_for_selector("#app", state="visible")
            assert "dashboard.html" in tab_a.url

            tab_b = context.new_page()
            tab_b.goto(f"{base_url}{DASHBOARD}")
            tab_b.wait_for_selector("#app", state="visible")
            assert "dashboard.html" in tab_b.url

            # Tab A logs out (storage is cleared for the whole origin)
            tab_a.evaluate("() => localStorage.removeItem('token')")
            assert tab_b.evaluate("() => localStorage.getItem('token')") is None

            # The stale tab only notices on its next document load ...
            tab_b.reload()
            tab_b.wait_for_url("**/login.html", timeout=25000)

            # ... and cannot claw the session back by re-entering the dashboard
            tab_b.goto(f"{base_url}{DASHBOARD}")
            tab_b.wait_for_url("**/login.html", timeout=25000)
        finally:
            context.close()

    def test_fresh_tab_after_logout_starts_signed_out(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")

        context = browser.new_context()
        try:
            _seed_token(context, base_url, test_user_token)
            first = context.new_page()
            first.goto(f"{base_url}{DASHBOARD}")
            first.wait_for_selector("#app", state="visible")

            first.evaluate("() => localStorage.removeItem('token')")
            new_tab = context.new_page()
            new_tab.goto(f"{base_url}{DASHBOARD}")
            new_tab.wait_for_url("**/login.html", timeout=25000)
        finally:
            context.close()


class TestSharedServiceWorker:
    def test_one_service_worker_is_shared_by_all_tabs(self, browser, base_url):
        context = browser.new_context()
        try:
            tab_a = context.new_page()
            tab_a.goto(f"{base_url}{ABOUT}")
            tab_a.wait_for_function(
                "() => !!navigator.serviceWorker.controller", timeout=25000
            )

            tab_b = context.new_page()
            tab_b.goto(f"{base_url}{ABOUT}")
            tab_b.wait_for_function(
                "() => !!navigator.serviceWorker.controller", timeout=25000
            )

            regs_a = tab_a.evaluate(
                "() => navigator.serviceWorker.getRegistrations().then(r => r.length)"
            )
            regs_b = tab_b.evaluate(
                "() => navigator.serviceWorker.getRegistrations().then(r => r.length)"
            )
            assert regs_a == 1, f"Tab A has {regs_a} service worker registrations"
            assert regs_b == 1, f"Tab B has {regs_b} service worker registrations"
            assert tab_a.evaluate("() => navigator.serviceWorker.controller.scriptURL") == \
                tab_b.evaluate("() => navigator.serviceWorker.controller.scriptURL")
        finally:
            context.close()
