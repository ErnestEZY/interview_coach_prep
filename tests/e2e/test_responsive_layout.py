"""Responsive layout coverage: phone portrait and tablet portrait/landscape.

Verifies that key pages render without horizontal overflow, keep their primary
controls reachable and tappable, and that the hero CTA pair stays symmetric at
every width between 320 and 1440 — single-line captions, equal heights, and a
centred pair, whether the two buttons share a row or each takes its own line.
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


# Widths where the hero column changes character: phone column, the `sm`
# breakpoint itself, tablet portrait and landscape, the `lg` floor where the
# hero splits into two columns, and a wide desktop.
CTA_WIDTHS = [
    pytest.param(320, 640, id="narrow-320"),
    pytest.param(390, 844, id="phone-390"),
    pytest.param(576, 800, id="sm-floor-576"),
    pytest.param(768, 1024, id="tablet-portrait-768"),
    pytest.param(992, 768, id="lg-floor-992"),
    pytest.param(1024, 768, id="tablet-landscape-1024"),
    pytest.param(1180, 820, id="tablet-landscape-1180"),
    pytest.param(1440, 900, id="desktop-1440"),
]

# A `btn-lg` with `py-3` measures ~64px. A caption that breaks onto a second
# line makes it ~94px, which is the number this guards against.
ONE_LINE_MAX_HEIGHT = 80

CTA_EDGES_JS = """() => {
  const primary = document.querySelector('#home-primary-cta');
  const secondary = document.querySelector('a[aria-label="Learn more about Interview Coach Prep"]');
  const row = primary.parentElement.getBoundingClientRect();
  const a = primary.getBoundingClientRect();
  const b = secondary.getBoundingClientRect();
  return { left: a.left - row.left, right: row.right - b.right };
}"""

@pytest.mark.parametrize("width,height", CTA_WIDTHS)
def test_hero_ctas_never_break_a_caption(browser, width, height):
    """The CTA pair stays symmetric however the window is squeezed.

    Reported from a narrowed desktop window: "Learn More About ICP" wrapped to
    two lines, and because the row let both buttons shrink, "Get Started"
    wrapped with it — two 94px buttons with broken captions where 64px would
    do. The pair is now `text-nowrap` + `flex-sm-wrap`: a caption never breaks,
    and a row that cannot hold both buttons moves one onto its own line rather
    than compressing the text. `justify-content-sm-center` keeps the pair, or
    the single stacked button, centred in the column.
    """
    context = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/")
        page.wait_for_selector("text=Master Your Next Interview")

        boxes = {}
        for name, selector in (
            ("primary", "#home-primary-cta"),
            ("secondary", 'a[aria-label="Learn more about Interview Coach Prep"]'),
        ):
            box = page.locator(selector).first.bounding_box()
            assert box, f"{name} CTA has no box at {width}x{height}"
            boxes[name] = box

        for name, box in boxes.items():
            assert box["height"] <= ONE_LINE_MAX_HEIGHT, (
                f"{name} CTA is {box['height']:.0f}px tall at {width}x{height}: "
                "its caption broke across two lines"
            )
            assert box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (
                f"{name} CTA hangs off the viewport at {width}x{height}: "
                f"x={box['x']:.0f} w={box['width']:.0f}"
            )

        assert abs(boxes["primary"]["height"] - boxes["secondary"]["height"]) <= 1, (
            f"the CTAs are different heights at {width}x{height} "
            f"({boxes['primary']['height']:.0f} vs {boxes['secondary']['height']:.0f}) "
            "— one caption wrapped and the other did not"
        )

        edges = page.evaluate(CTA_EDGES_JS)
        assert abs(edges["left"] - edges["right"]) <= 2, (
            f"the CTA pair sits off-centre at {width}x{height}: "
            f"{edges['left']:.1f}px left, {edges['right']:.1f}px right"
        )
    finally:
        context.close()
