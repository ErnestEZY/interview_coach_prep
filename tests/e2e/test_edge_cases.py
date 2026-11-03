"""Extreme edge cases: hostile input, corrupted state, interrupted flows,
extreme viewports and rapid connectivity flapping.

These complement the offline suites by attacking state rather than the
network: poisoned storage, garbage tokens, XSS payloads, navigations that
interrupt in-flight requests, 320px and 2560px canvases, and aggressive
offline/online toggling.
"""
import pytest

pytestmark = pytest.mark.e2e

LOGIN = "/static/pages/login.html"
XSS_PAYLOAD = '<img src=x onerror="window.__xss=1">'


def _open_login(page, base_url):
    page.goto(f"{base_url}{LOGIN}")
    page.wait_for_selector("text=Welcome Back")


class TestHostileInput:
    def test_xss_payload_never_executes(self, page, base_url):
        """A markup payload in the email field is rejected by native email
        validation: no request, no dialog, no script execution, no DOM injection."""
        dialogs = []
        login_requests = []
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        page.on(
            "request",
            lambda r: login_requests.append(r.url) if "/api/auth/login" in r.url else None,
        )
        _open_login(page, base_url)
        page.fill('input[name="email"]', XSS_PAYLOAD)
        page.fill('input[name="password"]', "Payload123!")
        assert page.evaluate(
            "document.querySelector('input[name=email]').validity.valid"
        ) is False, "Markup payload must fail the native email contract"
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(1000)
        assert dialogs == [], f"Script dialog fired: {dialogs}"
        assert page.evaluate("window.__xss") is None
        assert login_requests == [], f"Hostile input reached the API: {login_requests}"
        assert page.locator('.swal2-popup img[src="x"]').count() == 0
        assert "login.html" in page.url

    def test_oversized_paste_is_truncated_at_boundary(self, page, base_url):
        """A 5k-char paste must be cut at the field boundary before submit."""
        _open_login(page, base_url)
        page.fill('input[name="email"]', "z" * 5000)
        page.fill('input[name="password"]', "z" * 5000)
        assert len(page.input_value('input[name="email"]')) == 50
        assert len(page.input_value('input[name="password"]')) == 16

    def test_unicode_and_emoji_are_accepted_as_text(self, page, base_url):
        _open_login(page, base_url)
        page.fill('input[name="email"]', "tester+ünïcode@example.com")
        assert "ünïcode" in page.input_value('input[name="email"]')
        page.goto(f"{base_url}/static/pages/forgot_password.html")
        page.fill('input[name="email"]', "tester+ünïcode@example.com")
        assert page.input_value('input[name="email"]').startswith("tester+")


class TestCorruptedState:
    def test_garbage_token_redirects_to_login(self, browser, base_url):
        context = browser.new_context()
        context.add_init_script(
            "try { localStorage.setItem('token', 'garbage.token.value'); } catch (e) {}"
        )
        page = context.new_page()
        try:
            page.goto(f"{base_url}/static/pages/dashboard.html")
            page.wait_for_url("**/login.html", timeout=25000)
        finally:
            context.close()

    @pytest.mark.parametrize("bad", ["undefined", "null"])
    def test_sentinel_tokens_are_rejected(self, browser, base_url, bad):
        context = browser.new_context()
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{bad}'); }} catch (e) {{ }}"
        )
        page = context.new_page()
        try:
            page.goto(f"{base_url}/static/pages/dashboard.html")
            page.wait_for_url("**/login.html", timeout=20000)
        finally:
            context.close()

    def test_huge_localstorage_is_survivable(self, page, base_url):
        _open_login(page, base_url)
        page.evaluate(
            """() => {
                const chunk = 'x'.repeat(64 * 1024);
                for (let i = 0; i < 40; i++) {
                    try { localStorage.setItem('filler_' + i, chunk); }
                    catch (e) { break; }  // quota: stop quietly like the app would
                }
            }"""
        )
        page.reload()
        page.wait_for_selector("text=Welcome Back")
        # login.js wipes storage on mount; the page must still be usable
        page.locator(".btn-overlay-trigger").click()
        page.locator(".swal2-popup:has-text('Incomplete Fields')").wait_for(
            state="visible", timeout=10000
        )


class TestInterruptedFlows:
    def test_navigation_during_inflight_login_does_not_crash(self, page, base_url):
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def slow_login(route):
            try:
                page.wait_for_timeout(2500)
                route.fulfill(status=401, content_type="application/json",
                              body='{"detail": "Invalid credentials"}')
            except Exception:
                pass  # page navigated away: route may already be abandoned

        page.route("**/api/auth/login", slow_login)
        _open_login(page, base_url)
        page.fill('input[name="email"]', "interrupted@example.com")
        page.fill('input[name="password"]', "Interrupted1!")
        page.locator('button[type="submit"]').click(no_wait_after=True)
        page.goto(f"{base_url}/")
        page.wait_for_selector("text=Master Your Next Interview")
        assert errors == [], f"Uncaught errors: {errors}"

    def test_history_trap_blocks_back_and_pages_stay_usable(self, page, base_url):
        """app.js re-pushes the current entry on popstate for public pages so
        users cannot back into a signed-in page. Back must therefore keep the
        user in place, and the page must remain usable afterwards."""
        page.goto(f"{base_url}/")
        page.wait_for_selector("text=Master Your Next Interview")
        page.goto(f"{base_url}/static/pages/about.html")
        page.wait_for_selector("text=Career Launchpad")

        page.go_back()
        page.wait_for_timeout(800)
        assert "about.html" in page.url, f"History trap failed, left page: {page.url}"
        assert page.locator("text=Career Launchpad").count() == 1

        page.go_forward()
        page.wait_for_timeout(500)
        assert "about.html" in page.url

        # Fresh navigations still work after the blocked history moves
        page.goto(f"{base_url}{LOGIN}")
        page.wait_for_selector("text=Welcome Back")

    def test_rapid_offline_online_flapping_recovers(self, page, base_url):
        page.goto(f"{base_url}/")
        page.wait_for_selector("text=Master Your Next Interview")
        for _ in range(3):
            page.context.set_offline(True)
            page.wait_for_timeout(150)
            page.context.set_offline(False)
            page.wait_for_timeout(150)
        page.wait_for_selector("text=Master Your Next Interview", timeout=20000)
        page.wait_for_function("!document.querySelector('#offline-overlay.active')")


class TestExtremeViewports:
    @pytest.mark.parametrize(
        "label,width,height",
        [("tiny-320x568", 320, 568), ("ultrawide-2560x1080", 2560, 1080)],
    )
    def test_no_horizontal_overflow(self, browser, base_url, label, width, height):
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        try:
            page.goto(f"{base_url}/")
            page.wait_for_selector("text=Master Your Next Interview")
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - window.innerWidth"
            )
            assert overflow <= 1, f"{label}: home overflows by {overflow}px"

            page.goto(f"{base_url}{LOGIN}")
            page.wait_for_selector("text=Welcome Back")
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - window.innerWidth"
            )
            assert overflow <= 1, f"{label}: login overflows by {overflow}px"
        finally:
            context.close()
