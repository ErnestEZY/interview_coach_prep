"""Responsive layout coverage: phone portrait and tablet portrait/landscape.

Verifies that key pages render without horizontal overflow, keep their primary
controls reachable and tappable, and that the hero CTA buttons only stretch
full-width below the Bootstrap `sm` breakpoint (class `w-100 w-sm-auto`).
"""
import os

import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")

PHONE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

PHONE_PORTRAIT = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 3,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": PHONE_UA,
}
TABLET_PORTRAIT = {
    "viewport": {"width": 768, "height": 1024},
    "device_scale_factor": 2,
    "is_mobile": False,
    "has_touch": True,
}
TABLET_LANDSCAPE = {
    "viewport": {"width": 1024, "height": 768},
    "device_scale_factor": 2,
    "is_mobile": False,
    "has_touch": True,
}

VIEWPORTS = [
    pytest.param(PHONE_PORTRAIT, id="phone-portrait-390x844"),
    pytest.param(TABLET_PORTRAIT, id="tablet-portrait-768x1024"),
    pytest.param(TABLET_LANDSCAPE, id="tablet-landscape-1024x768"),
]

PAGES = [
    "/",
    "/static/pages/login.html",
    "/static/pages/register.html",
    "/static/pages/about.html",
]


@pytest.fixture(params=VIEWPORTS)
def responsive_page(request, browser):
    context = browser.new_context(**request.param)
    page = context.new_page()
    yield page
    context.close()


def _tap(page, locator):
    """Tap the element centre, like a finger on a touch screen."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    assert box, "element has no bounding box to tap"
    page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def _assert_within_viewport_width(page, locator):
    box = locator.bounding_box()
    assert box, "element has no bounding box"
    width = page.viewport_size["width"]
    assert box["x"] >= -1, f"element starts left of viewport: x={box['x']}"
    assert box["x"] + box["width"] <= width + 1, (
        f"element overflows right edge: x+w={box['x'] + box['width']} vs viewport {width}"
    )


def test_no_horizontal_overflow(responsive_page):
    page = responsive_page
    for path in PAGES:
        page.goto(f"{BASE_URL}{path}")
        page.wait_for_load_state("load")
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, (
            f"{path} overflows horizontally by {overflow}px at "
            f"{page.viewport_size['width']}x{page.viewport_size['height']}"
        )


def test_home_hero_buttons_reachable_and_tappable(responsive_page):
    page = responsive_page
    page.goto(f"{BASE_URL}/")
    page.wait_for_selector("text=Master Your Next Interview")

    get_started = page.locator('a:has-text("Get Started")').first
    learn_more = page.locator('a:has-text("Learn More About ICP")').first
    for button in (get_started, learn_more):
        button.wait_for(state="visible")
        _assert_within_viewport_width(page, button)

    # Finger-tap the Learn More CTA and confirm the About page opens.
    _tap(page, learn_more)
    page.wait_for_url("**/about.html")
    assert "Career Launchpad" in page.inner_text("body")


def test_login_form_usable(responsive_page):
    page = responsive_page
    page.goto(f"{BASE_URL}/static/pages/login.html")
    page.wait_for_selector("text=Welcome Back")

    for selector in ('input[type="email"]', 'input[type="password"]'):
        field = page.locator(selector).first
        field.wait_for(state="visible")
        _assert_within_viewport_width(page, field)

    forgot = page.locator('a:has-text("Forgot Password?")').first
    forgot.wait_for(state="visible")
    _assert_within_viewport_width(page, forgot)

    # Finger-tap "Forgot Password?" and confirm the recovery page opens.
    _tap(page, forgot)
    page.wait_for_url("**/forgot_password.html")
    page.wait_for_selector("text=Send Reset Link")


def test_cta_full_width_only_on_phone(browser):
    """Below Bootstrap `sm` (576px) the CTAs stretch full-width; above they don't."""
    measurements = {}
    for name, profile in (
        ("phone", PHONE_PORTRAIT),
        ("tablet-portrait", TABLET_PORTRAIT),
        ("tablet-landscape", TABLET_LANDSCAPE),
    ):
        context = browser.new_context(**profile)
        try:
            page = context.new_page()
            page.goto(f"{BASE_URL}/")
            page.wait_for_selector("text=Master Your Next Interview")
            box = page.locator('a:has-text("Learn More About ICP")').first.bounding_box()
            measurements[name] = box["width"]
        finally:
            context.close()

    phone_width = PHONE_PORTRAIT["viewport"]["width"]
    portrait_width = TABLET_PORTRAIT["viewport"]["width"]
    landscape_width = TABLET_LANDSCAPE["viewport"]["width"]

    assert measurements["phone"] >= phone_width * 0.85, (
        f"phone CTA should be full-width, got {measurements['phone']} of {phone_width}"
    )
    assert measurements["tablet-portrait"] <= portrait_width * 0.6, (
        f"tablet-portrait CTA should be content-width, got {measurements['tablet-portrait']}"
    )
    assert measurements["tablet-landscape"] <= landscape_width * 0.6, (
        f"tablet-landscape CTA should be content-width, got {measurements['tablet-landscape']}"
    )
