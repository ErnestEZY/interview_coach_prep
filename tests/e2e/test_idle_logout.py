"""Idle logout: a session nobody is using ends itself and says why.

This is the second clock on a session. The first is the token's own `exp`,
which every page counts down into the badge in the corner. This one measures
input: a tab with no pointer, key, scroll or touch activity for an hour signs
itself out and lands on the login page under a notice that stays put until it
is dismissed.

The interval ships at one hour. These tests drive the same code path in
seconds through `window.__ICP_IDLE_TIMEOUT_MS`, which `app.min.js` reads while
it parses — nothing in the application sets it.
"""
import os
import re

import httpx
import pytest
from playwright.sync_api import expect

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")

NOTICE = "#idle-logout-notice"
NOTICE_TEXT = "logged out due to inactivity"
IDLE_LOGIN_URL = re.compile(r"/static/pages/login\.html\?reason=idle$")
IDLE_ADMIN_LOGIN_URL = re.compile(r"/static/pages/icp-admin-auth-[^/]+\?reason=idle$")
ONE_HOUR_MS = 60 * 60 * 1000


def _require_valid_token(token, who):
    """Skip - loudly - when the backend cannot vouch for the token.

    Without this the suites below would fail on an expired token with a
    timeout, which reads like a broken idle timer rather than a stale fixture.
    """
    if not token:
        pytest.skip(f"No {who} token available — backend may be down")
    try:
        response = httpx.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"backend unreachable: {exc}")
    if response.status_code != 200:
        pytest.skip(f"{who} token rejected by /api/auth/me ({response.status_code})")


@pytest.fixture
def idle_clock(browser, test_user_token):
    """Hands out signed-in contexts whose idle timeout is set in milliseconds."""
    _require_valid_token(test_user_token, "test user")
    contexts = []

    def _make(timeout_ms):
        context = browser.new_context()
        # Both values belong in the init script: app.min.js reads the token and
        # the timeout while parsing, so anything set after navigation is late.
        context.add_init_script(
            f"window.__ICP_IDLE_TIMEOUT_MS = {timeout_ms};\n"
            f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{}}"
        )
        contexts.append(context)
        return context

    yield _make
    for context in contexts:
        context.close()


def test_idle_session_ends_at_the_login_page_with_a_sticky_notice(idle_clock):
    """After the idle interval: no token, the login page, and a visible reason."""
    context = idle_clock(1200)
    page = context.new_page()
    page.goto(f"{BASE_URL}/static/pages/dashboard.html")

    page.wait_for_url(IDLE_LOGIN_URL, timeout=20000)

    notice = page.locator(NOTICE)
    expect(notice).to_be_visible()
    expect(notice).to_contain_text(NOTICE_TEXT)
    # A banner the page scrolls away from is not the notification that was
    # asked for, so the element itself has to be sticky, not merely fixed.
    assert page.evaluate(
        "getComputedStyle(document.getElementById('idle-logout-notice')).position"
    ) == "sticky", "the notice must stay put while the login form scrolls"
    box = notice.bounding_box()
    assert box and box["y"] <= 8, f"the notice must sit at the top of the page, got y={box}"

    # It is a status message, not decoration: an assistive technology that
    # polls nothing must still be told the session ended.
    assert notice.get_attribute("role") == "status"

    # The session is gone, so a refresh cannot resurrect it.
    assert page.evaluate("localStorage.getItem('token')") is None


def test_activity_keeps_the_session_alive(idle_clock):
    """Input resets the clock: 4s of use outlives a 2.5s timeout.

    A watcher that counted time since page load instead of since the last
    event would pass every other test in this file and fail this one.
    """
    context = idle_clock(2500)
    page = context.new_page()
    page.goto(f"{BASE_URL}/static/pages/dashboard.html")
    expect(page.locator("body")).to_be_visible()

    for step in range(10):
        page.mouse.move(120 + (step % 2) * 40, 160)
        page.wait_for_timeout(400)

    assert "login.html" not in page.url, "activity did not reset the idle clock"
    assert page.locator(NOTICE).count() == 0


def test_a_signed_out_page_never_starts_the_watch(browser):
    """No token, no session to end — the landing page must not redirect."""
    context = browser.new_context()
    # The timeout is set, the token is not: only the second one can arm the
    # watcher, so this is the case where nothing may happen.
    context.add_init_script("window.__ICP_IDLE_TIMEOUT_MS = 600;")
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/")
        page.wait_for_selector("text=Master Your Next Interview")

        assert page.evaluate("window.icp.idle.isWatching()") is False
        page.wait_for_timeout(1500)
        assert "login.html" not in page.url, "a signed-out page redirected itself"
    finally:
        context.close()


def test_the_shipped_idle_timeout_is_one_hour(browser):
    """The constant that ships, not the test hook: an hour in milliseconds."""
    context = browser.new_context()
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/")
        assert page.evaluate("window.icp.idle.timeoutMs") == ONE_HOUR_MS
    finally:
        context.close()


def test_the_notice_only_appears_on_a_login_page(browser):
    """The reason is in the URL; only a login page may act on it."""
    context = browser.new_context()
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/?reason=idle")
        page.wait_for_selector("text=Master Your Next Interview")
        assert page.locator(NOTICE).count() == 0
    finally:
        context.close()


def test_dismissing_the_notice_clears_the_reason(browser):
    """Dismissal is permanent: a reload must not bring the banner back."""
    context = browser.new_context()
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/static/pages/login.html?reason=idle")
        page.wait_for_selector("text=Welcome Back")

        notice = page.locator(NOTICE)
        expect(notice).to_be_visible()
        page.get_by_role("button", name="Dismiss inactivity notice").click()
        expect(notice).to_have_count(0)
        assert "reason=idle" not in page.url, "dismissing left the reason in the URL"

        page.reload()
        page.wait_for_selector("text=Welcome Back")
        assert page.locator(NOTICE).count() == 0, "the notice came back after a reload"
    finally:
        context.close()


def test_admin_idle_logout_lands_on_the_admin_login(browser, admin_user_token):
    """An idle administrator is returned to the admin door, not the user one."""
    _require_valid_token(admin_user_token, "admin")
    context = browser.new_context()
    context.add_init_script(
        "window.__ICP_IDLE_TIMEOUT_MS = 1200;\n"
        f"try {{ localStorage.setItem('token', '{admin_user_token}'); }} catch (e) {{}}"
    )
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/static/pages/icp-admin-portal-5e6a1c3d.html")
        page.wait_for_url(IDLE_ADMIN_LOGIN_URL, timeout=20000)
        expect(page.locator(NOTICE)).to_be_visible()
        expect(page.locator(NOTICE)).to_contain_text(NOTICE_TEXT)
    finally:
        context.close()
