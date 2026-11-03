"""Speed budgets and stability soak for the E2E surface.

Budgets are deliberately generous so they hold on slow CI runners while still
catching regressions of the "10x slower" kind: navigation timing, API latency,
repeated-load degradation, a 5-cycle navigation soak and reload stability.
"""
import time

import pytest

pytestmark = pytest.mark.e2e

HOME = "/"
LOGIN = "/static/pages/login.html"
ABOUT = "/static/pages/about.html"
DASHBOARD = "/static/pages/dashboard.html"
REGISTER = "/static/pages/register.html"

TTFB_BUDGET_MS = 3000
DCL_BUDGET_MS = 12000
LOAD_BUDGET_MS = 15000
API_BUDGET_MS = 4000


def _timing(page):
    return page.evaluate(
        """() => {
            const n = performance.getEntriesByType('navigation')[0];
            return {
                ttfb: n.responseStart - n.startTime,
                dcl: n.domContentLoadedEventEnd - n.startTime,
                load: n.loadEventEnd - n.startTime,
            };
        }"""
    )


class TestSpeedBudgets:
    def test_home_navigation_within_budget(self, page, base_url):
        page.goto(f"{base_url}{HOME}", wait_until="load")
        page.wait_for_selector("text=Master Your Next Interview")
        timing = _timing(page)
        assert timing["ttfb"] < TTFB_BUDGET_MS, f"TTFB {timing['ttfb']:.0f}ms"
        assert timing["dcl"] < DCL_BUDGET_MS, f"DCL {timing['dcl']:.0f}ms"
        assert timing["load"] < LOAD_BUDGET_MS, f"load {timing['load']:.0f}ms"

    def test_login_page_navigation_within_budget(self, page, base_url):
        page.goto(f"{base_url}{LOGIN}", wait_until="load")
        page.wait_for_selector("text=Welcome Back")
        timing = _timing(page)
        assert timing["ttfb"] < TTFB_BUDGET_MS, f"TTFB {timing['ttfb']:.0f}ms"
        assert timing["dcl"] < DCL_BUDGET_MS, f"DCL {timing['dcl']:.0f}ms"

    def test_public_api_latency_budget(self, page, base_url):
        start = time.monotonic()
        response = page.request.get(f"{base_url}/api/auth/config")
        elapsed_ms = (time.monotonic() - start) * 1000
        assert response.status == 200
        assert elapsed_ms < API_BUDGET_MS, f"/api/auth/config took {elapsed_ms:.0f}ms"

    def test_authenticated_api_latency_budget(self, page, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")
        start = time.monotonic()
        response = page.request.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        assert response.status == 200
        assert elapsed_ms < API_BUDGET_MS, f"/api/auth/me took {elapsed_ms:.0f}ms"


class TestLoadLite:
    def test_repeated_home_loads_do_not_degrade(self, page, base_url):
        durations = []
        for _ in range(3):
            start = time.monotonic()
            page.goto(f"{base_url}{HOME}", wait_until="load")
            page.wait_for_selector("text=Master Your Next Interview")
            durations.append(time.monotonic() - start)
        assert durations[-1] < durations[0] * 2 + 2.0, (
            f"Load time degraded across repeats: "
            f"{[round(d, 2) for d in durations]}s"
        )

    def test_five_sequential_api_calls_finish_quickly(self, page, base_url):
        start = time.monotonic()
        for _ in range(5):
            assert page.request.get(f"{base_url}/api/auth/config").status == 200
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"5 sequential config calls took {elapsed:.2f}s"


class TestStabilitySoak:
    def test_five_navigation_cycles_are_stable(self, page, base_url):
        errors, server_errors = [], []

        def on_response(response):
            if response.status >= 500:
                server_errors.append((response.status, response.url))

        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", on_response)

        for _ in range(5):
            for route in (HOME, ABOUT, LOGIN, REGISTER):
                page.goto(f"{base_url}{route}", wait_until="domcontentloaded")
                page.wait_for_selector("#app", state="visible")

        assert errors == [], f"Uncaught page errors: {errors[:5]}"
        assert server_errors == [], f"5xx responses during soak: {server_errors[:5]}"

    def test_five_reloads_keep_authenticated_session(self, browser, base_url, test_user_token):
        if not test_user_token:
            pytest.skip("No test user token available")

        context = browser.new_context()
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
        )
        try:
            page = context.new_page()
            for cycle in range(5):
                page.goto(f"{base_url}{DASHBOARD}")
                page.wait_for_selector("#app", state="visible")
                assert "dashboard.html" in page.url, f"Lost session on reload {cycle + 1}"
        finally:
            context.close()
