"""Mobile device emulation: the physical-phone walkthrough as an automated test.

Mirrors the ADB phone demo (home -> about -> login -> forgot password) on an
emulated Pixel 7 viewport with real touch input, so the same user journey is
repeatable on every run and in CI.
"""
import os

import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")

# Pixel 7 profile: 412x915 CSS viewport, 2.625x density, mobile + touch.
PIXEL7 = {
    "viewport": {"width": 412, "height": 915},
    "device_scale_factor": 2.625,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
}


@pytest.fixture
def mobile_page(browser):
    os.makedirs("mobile_demo", exist_ok=True)
    context = browser.new_context(**PIXEL7)
    # Record a debuggable trace of the whole journey (screenshots, DOM
    # snapshots, source frames) for the Playwright trace viewer.
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    yield page
    context.tracing.stop(path="mobile_demo/journey_trace.zip")
    context.close()


def _tap(page, locator):
    """Tap the element centre, like a finger on a phone screen."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    assert box, "element has no bounding box to tap"
    page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_phone_journey_home_about_login_forgot(mobile_page):
    page = mobile_page

    # 1. Home, rendered in the mobile layout
    page.goto(f"{BASE_URL}/")
    page.wait_for_selector("text=Master Your Next Interview")

    # 2. Finger-tap "Learn More About ICP" -> About page
    _tap(page, page.locator('a:has-text("Learn More About ICP")'))
    page.wait_for_url("**/about.html")
    assert "Career Launchpad" in page.inner_text("body")
    page.screenshot(path="mobile_demo/about_page.png")

    # 3. Finger-tap the header Login link -> Login page
    _tap(page, page.locator('a[href*="login.html"]').first)
    page.wait_for_url("**/login.html")
    page.wait_for_selector("text=Welcome Back")

    # 4. Finger-tap "Forgot Password?" -> recovery page
    _tap(page, page.locator('a:has-text("Forgot Password?")'))
    page.wait_for_url("**/forgot_password.html")
    page.wait_for_selector("text=Send Reset Link")
    page.screenshot(path="mobile_demo/forgot_page.png")
