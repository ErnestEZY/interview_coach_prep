"""Offline behavior across viewports: desktop, phone portrait, tablet portrait/landscape.

Covers:
  - Cold offline: navigation fails before any service worker exists, then
    recovers as soon as connectivity returns.
  - Warm offline (PWA): the service worker serves the cached app shell for
    dashboard-type pages, while auth pages (never cached by sw.js) return its
    503 "Service unavailable" notice instead of stale HTML.
  - Degraded forms: signing in while the API is unreachable surfaces the
    app's "Login Failed" dialog; a real browser-level disconnect instead
    raises the app's full-screen "You're Offline" wall, which must lift
    automatically once connectivity returns.
"""
import os

import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")

PHONE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

PROFILES = [
    pytest.param({"viewport": {"width": 1280, "height": 800}}, id="desktop-1280x800"),
    pytest.param(
        {
            "viewport": {"width": 390, "height": 844},
            "device_scale_factor": 3,
            "is_mobile": True,
            "has_touch": True,
            "user_agent": PHONE_UA,
        },
        id="phone-portrait-390x844",
    ),
    pytest.param(
        {"viewport": {"width": 768, "height": 1024}, "has_touch": True},
        id="tablet-portrait-768x1024",
    ),
    pytest.param(
        {"viewport": {"width": 1024, "height": 768}, "has_touch": True},
        id="tablet-landscape-1024x768",
    ),
]

# Waits for the service worker to activate and finish precaching the app shell.
SW_READY_JS = """
(async () => {
  if (!('serviceWorker' in navigator)) return 'no-sw';
  const timeout = new Promise(r => setTimeout(() => r('ready-timeout'), 20000));
  const ready = (async () => {
    await navigator.serviceWorker.ready;
    for (let i = 0; i < 75; i++) {
      const names = (await caches.keys()).filter(n => n.startsWith('icp-cache'));
      for (const name of names) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        // The page must be SW-controlled, not just have a warm cache,
        // otherwise offline navigations bypass the worker entirely.
        if (navigator.serviceWorker.controller &&
            keys.some(req => req.url.includes('dashboard.html'))) {
          return 'ready:' + keys.length;
        }
      }
      await new Promise(r => setTimeout(r, 200));
    }
    return 'cache-timeout';
  })();
  return Promise.race([ready, timeout]);
})()
"""


@pytest.fixture(params=PROFILES)
def viewport_profile(request):
    return request.param


def test_cold_offline_fails_then_recovers(browser, viewport_profile):
    """Without a cached shell, offline navigation must fail cleanly and the
    app must come back online without user intervention."""
    context = browser.new_context(**viewport_profile)
    page = context.new_page()
    context.set_offline(True)
    raised = False
    try:
        page.goto(f"{BASE_URL}/static/pages/login.html", timeout=15000)
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

    context.set_offline(False)
    page.goto(f"{BASE_URL}/static/pages/login.html")
    page.wait_for_selector("text=Welcome Back")
    context.close()


def test_warm_offline_serves_cached_shell_but_not_auth_pages(
    browser, viewport_profile, test_user_token
):
    """After the service worker precaches the app, the dashboard shell loads
    offline from cache while auth pages fall back to the SW's 503 notice."""
    if not test_user_token:
        pytest.skip("No test user token available")
    context = browser.new_context(**viewport_profile)
    context.add_init_script(
        f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
    )
    page = context.new_page()
    page.goto(f"{BASE_URL}/static/pages/dashboard.html")

    sw_state = page.evaluate(SW_READY_JS)
    assert str(sw_state).startswith("ready:"), f"Service worker precache failed: {sw_state}"

    context.set_offline(True)
    # Playwright attaches no Response object when the service worker answers a
    # navigation, so verify the cached shell through the SW fetch pipeline.
    page.goto(f"{BASE_URL}/static/pages/dashboard.html", wait_until="domcontentloaded")
    assert 'id="app"' in page.content(), "Cached shell was not served offline"

    shell_status = page.evaluate(
        "fetch('/static/pages/dashboard.html').then(r => r.status)"
    )
    assert shell_status == 200, f"Cached shell fetch failed offline: {shell_status}"

    # login.html is in sw.js NEVER_CACHE: through the worker it must not serve
    # stale HTML, only the plain 503 service notice. Probe with fetch rather
    # than a navigation: the app's own inline token guards (dashboard.html
    # redirects to login, login.html wipes the token) bounce navigations away
    # while offline, so navigation outcomes are not a stable contract.
    login_probe = page.evaluate(
        "fetch('/static/pages/login.html').then(async r => r.status + '|' + await r.text())"
    )
    assert str(login_probe).startswith("503|"), f"Auth page must not be cached: {login_probe}"
    assert "Service unavailable" in login_probe

    context.set_offline(False)
    # Recover in a fresh page so the previous page's 'online' handler (which
    # forces a reload) cannot cancel this navigation.
    recovered = context.new_page()
    recovered.goto(f"{BASE_URL}/")
    recovered.wait_for_selector("text=Master Your Next Interview")
    context.close()


def test_login_submit_with_api_down_shows_network_error(browser, viewport_profile):
    """API outage: clicking Sign In must surface the app's error dialog."""
    context = browser.new_context(**viewport_profile)
    page = context.new_page()
    page.goto(f"{BASE_URL}/static/pages/login.html")
    page.wait_for_selector("text=Welcome Back")

    page.route("**/api/**", lambda route: route.abort())
    page.fill('input[type="email"]', "offline@example.com")
    page.fill('input[type="password"]', "offline-pass-123")
    page.locator('button:has-text("Sign In")').click()
    page.wait_for_selector(".swal2-popup:has-text('Login Failed')", timeout=20000)
    context.close()


def test_fully_offline_shows_blocking_overlay_then_recovers(browser, viewport_profile):
    """A browser-level disconnect raises the app's full-screen offline wall,
    which blocks the form until connectivity returns."""
    context = browser.new_context(**viewport_profile)
    page = context.new_page()
    page.goto(f"{BASE_URL}/static/pages/login.html")
    page.wait_for_selector("text=Welcome Back")

    context.set_offline(True)
    overlay = page.locator("#offline-overlay.active")
    overlay.wait_for(state="visible", timeout=10000)
    assert "You're Offline" in overlay.inner_text()
    assert overlay.locator('button:has-text("Try Reconnecting")').is_visible()

    # While the wall is up it intentionally intercepts taps on the form.
    with pytest.raises(Exception):
        page.click('button:has-text("Sign In")', trial=True, timeout=3000)

    context.set_offline(False)
    page.wait_for_function("!document.querySelector('#offline-overlay.active')")
    page.fill('input[type="email"]', "offline@example.com")
    page.fill('input[type="password"]', "offline-pass-123")
    # The form is interactive again: the trial click passes actionability.
    page.click('button:has-text("Sign In")', trial=True, timeout=5000)
    context.close()
