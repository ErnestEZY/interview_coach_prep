"""
E2E Tests — Resume preview sizing, full screen and section tabs.

The preview is one fixed A4 sheet (210x297mm = 793.7x1122.5 CSS px at 96dpi)
drawn through a single scale factor measured from the live container. These
tests assert the outcome the user cares about instead of pinning CSS rules:

  * the sheet is as large as the panel physically allows (within 2px),
  * it is never clipped on the right, and never scrolls horizontally,
  * that holds on a real device profile per class (phone, foldable, tablet,
    both orientations) and at every width from 320px to 1920px, not only at
    the widths Bootstrap defines breakpoints for,
  * it re-measures on every resize / orientation change,
  * full screen covers the viewport, paints above the navbar, locks scrolling,
    traps focus and closes on Escape,
  * no section tab is hidden or clipped at any width,
  * typed data reaches the sheet, long unbroken strings wrap, and multi-page
    content paginates without changing the zoom.

Regression context: the previous breakpoint rules rendered the sheet at 254px
on a 768px tablet (40% of the panel), at 0.32 scale on <=991px, and pushed a
20px overflow past the right edge at 1280/1440.
"""
import os

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")
BUILDER_PATH = "/static/pages/resume_builder.html"

# A4 at the CSS reference resolution.
A4_W = 210 * 96 / 25.4
A4_H = 297 * 96 / 25.4

# (width, height, minimum acceptable sheet width). The floor encodes "this is a
# readable page, not a thumbnail"; fit is asserted separately against the live
# panel width, so the floor only guards against a shrink regression.
VIEWPORTS = [
    pytest.param(360, 800, 290, id="phone-360x800"),
    pytest.param(390, 844, 310, id="phone-390x844"),
    pytest.param(768, 1024, 600, id="tablet-768x1024"),
    pytest.param(1024, 768, 850, id="tablet-landscape-1024x768"),
    pytest.param(1280, 800, 500, id="laptop-1280x800"),
    pytest.param(1440, 900, 590, id="desktop-1440x900"),
    pytest.param(1920, 1080, 830, id="wide-1920x1080"),
]

TAB_VIEWPORTS = [
    pytest.param(360, 800, id="phone-360x800"),
    pytest.param(768, 1024, id="tablet-768x1024"),
    pytest.param(1280, 800, id="laptop-1280x800"),
]

# Every width a window can realistically be dragged to, not just the handful of
# widths Bootstrap has breakpoints for. The step is deliberately smaller than
# any plausible breakpoint gap: an 8px stride means no width in 320..1920 is
# more than 8px away from a measurement, so a rule that only misbehaves in a
# narrow interval cannot slip between samples.
SIZE_SWEEP_WIDTHS = list(range(320, 1921, 8))

# Short viewports deserve their own pass: laptops with browser chrome open, and
# phones held sideways, leave very little height for a fixed-height panel.
SHORT_VIEWPORTS = [
    pytest.param(1280, 600, id="laptop-short-1280x600"),
    pytest.param(1024, 480, id="tablet-landscape-1024x480"),
    pytest.param(900, 420, id="small-landscape-900x420"),
    pytest.param(844, 390, id="phone-landscape-844x390"),
    pytest.param(740, 360, id="phone-landscape-740x360"),
]

# One real profile per device class, including the two awkward extremes: the
# narrowest phone (320px) and a very short landscape phone (293px).
DEVICE_PROFILES = [
    "iPhone SE",                  # 320x568  smallest phone still in use
    "iPhone 13",                  # 390x664  baseline modern phone
    "iPhone 14 Pro Max",          # 430x740  largest phone
    "Galaxy S9+",                 # 320x658  narrow Android
    "Pixel 5",                    # 393x727  baseline Android
    "Galaxy Z Fold 6 Cover",      # 484x1112 tall and narrow foldable
    "iPad Mini",                  # 768x1024 small tablet
    "iPad Pro 11",                # 834x1194 large tablet
    "Pixel 5 landscape",          # 802x293  shortest viewport Playwright knows
    "iPhone 13 landscape",        # 750x342  phone held sideways
]

TAB_IDS = [
    "pills-basics-tab",
    "pills-edu-tab",
    "pills-exp-tab",
    "pills-projects-tab",
    "pills-skills-tab",
    "pills-others-tab",
    "pills-extra-tab",
]
TAB_PANES = {
    "pills-basics-tab": "tab-basics",
    "pills-edu-tab": "tab-edu",
    "pills-exp-tab": "tab-exp",
    "pills-projects-tab": "tab-projects",
    "pills-skills-tab": "tab-skills",
    "pills-others-tab": "tab-others",
    "pills-extra-tab": "tab-extra",
}


# ── Probes (run in the page) ───────────────────────────────────────────────

GEOMETRY_JS = """() => {
  const wrap = document.querySelector('.resume-preview-wrapper');
  const stage = document.querySelector('.resume-preview-stage');
  const cont = document.querySelector('.resume-preview-container');
  const tmpl = document.querySelector('#resume-template');
  if (!wrap || !stage || !cont) return null;
  const cs = getComputedStyle(wrap);
  const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
  const padY = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const wr = wrap.getBoundingClientRect();
  const sr = stage.getBoundingClientRect();
  const cr = cont.getBoundingClientRect();
  return {
    availW: wrap.clientWidth - padX,
    availH: wrap.clientHeight - padY,
    sheetW: sr.width,
    sheetH: sr.height,
    leftGap: sr.left - wr.left,
    rightGap: wr.right - sr.right,
    scale: parseFloat(stage.style.getPropertyValue('--preview-scale')) || 0,
    wrapOverflowX: wrap.scrollWidth - wrap.clientWidth,
    wrapOverflowY: wrap.scrollHeight - wrap.clientHeight,
    // Measured against clientWidth, not innerWidth. innerWidth includes a
    // classic scrollbar (8px on a headed Windows Firefox) while scrollWidth
    // never does, so the innerWidth form loses exactly the scrollbar width of
    // real overflow — the page can spill 8px and still report 0.
    docOverflowX: Math.max(0, document.documentElement.scrollWidth
                              - document.documentElement.clientWidth),
    templateOverflowX: tmpl ? tmpl.scrollWidth - tmpl.clientWidth : 0,
    templateTransform: tmpl ? tmpl.style.transform : '',
    container: { x: cr.x, y: cr.y, w: cr.width, h: cr.height },
    isFullscreen: cont.classList.contains('preview-fullscreen'),
    role: cont.getAttribute('role'),
    ariaModal: cont.getAttribute('aria-modal'),
    ariaLabel: cont.getAttribute('aria-label'),
    bodyOverflow: getComputedStyle(document.body).overflow,
    htmlOverflow: getComputedStyle(document.documentElement).overflow,
    fitModeLabel: (() => {
      const b = document.querySelector('.preview-fitmode-btn');
      return b ? b.textContent.trim() : null;
    })(),
  };
}"""

FIT_JS = """() => {
  const wrap = document.querySelector('.resume-preview-wrapper');
  const stage = document.querySelector('.resume-preview-stage');
  if (!wrap || !stage) return false;
  const cs = getComputedStyle(wrap);
  const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
  const avail = wrap.clientWidth - padX;
  if (avail < 100) return false;
  return Math.abs(stage.getBoundingClientRect().width - avail) <= 2;
}"""

TAB_STRIP_JS = """() => {
  const strip = document.querySelector('#pills-tab');
  if (!strip) return null;
  const sr = strip.getBoundingClientRect();
  const cs = getComputedStyle(strip);
  return {
    left: sr.left,
    right: sr.right,
    height: sr.height,
    scrollWidth: strip.scrollWidth,
    clientWidth: strip.clientWidth,
    scrollHeight: strip.scrollHeight,
    clientHeight: strip.clientHeight,
    overflowX: cs.overflowX,
    tabs: Array.from(strip.querySelectorAll('[role="tab"]')).map((t) => {
      const r = t.getBoundingClientRect();
      const tcs = getComputedStyle(t);
      return {
        id: t.id,
        text: t.textContent.trim(),
        left: r.left,
        right: r.right,
        top: Math.round(r.top),
        width: r.width,
        height: r.height,
        selected: t.getAttribute('aria-selected') === 'true',
        tabindex: t.tabIndex,
        fontSize: parseFloat(tcs.fontSize),
      };
    }),
  };
}"""


# ── Fixtures & helpers ─────────────────────────────────────────────────────

@pytest.fixture
def preview_page(browser, base_url, test_user_token):
    """Factory for an authenticated resume-builder page at a given viewport.

    `authenticated_page` from conftest pins one viewport, so responsive work
    needs its own context factory. `base_url` (not the module constant) keeps
    WebKit-on-Windows working, where loopback is unreachable. Every page is
    loaded and settled (fit applied, loader gone) before it is handed over.
    """
    if not test_user_token:
        pytest.skip("No test user token — backend unreachable or registration failed")

    contexts = []

    def open_builder(width, height, **context_kwargs):
        context = browser.new_context(
            viewport={"width": width, "height": height}, **context_kwargs
        )
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
        )
        page = context.new_page()
        contexts.append(context)
        page.goto(f"{base_url}{BUILDER_PATH}")
        assert "/login.html" not in page.url, "builder redirected to login — token rejected"
        page.wait_for_selector("#resume-template", state="attached", timeout=20000)
        page.wait_for_function(FIT_JS, timeout=20000)
        page.wait_for_function(
            "() => !document.querySelector('#global-loader')", timeout=20000
        )
        return page

    yield open_builder
    for context in contexts:
        context.close()


def geometry(page):
    data = page.evaluate(GEOMETRY_JS)
    assert data, "preview elements missing from the page — did the template change?"
    return data


def wait_for_fit(page, timeout=10000):
    """Wait until the sheet has re-measured to the current panel width."""
    page.wait_for_function(FIT_JS, timeout=timeout)


def assert_sheet_fills_panel(g, label, min_sheet_w=250):
    """The invariants every device and every width must satisfy.

    Kept in one place so the viewport matrix, the width sweep and the device
    profiles cannot quietly drift into asserting different things.
    """
    assert abs(g["sheetW"] - g["availW"]) <= 2, (
        f"{label}: sheet {g['sheetW']:.1f}px does not fill the "
        f"{g['availW']:.1f}px panel (scale {g['scale']})"
    )
    assert g["leftGap"] >= -1, (
        f"{label}: sheet starts {g['leftGap']:.1f}px left of the panel"
    )
    assert g["rightGap"] >= -1, (
        f"{label}: sheet ends {g['rightGap']:.1f}px past the panel"
    )
    assert g["wrapOverflowX"] <= 1, (
        f"{label}: preview scrolls sideways by {g['wrapOverflowX']}px"
    )
    assert g["docOverflowX"] <= 1, (
        f"{label}: page overflows sideways by {g['docOverflowX']}px"
    )
    assert abs(g["sheetH"] / g["sheetW"] - A4_H / A4_W) < 0.01, (
        f"{label}: sheet is not A4-proportioned ({g['sheetW']:.0f}x{g['sheetH']:.0f})"
    )
    assert g["sheetW"] >= min_sheet_w, (
        f"{label}: sheet is only {g['sheetW']:.1f}px wide — expected "
        f">= {min_sheet_w}px"
    )
    assert g["scale"] > 0.2, f"{label}: scale {g['scale']} is a thumbnail"


def assert_tab_strip_readable(strip, label):
    """No section tab may be hidden, scrolled out or crushed as width changes."""
    assert len(strip["tabs"]) == len(TAB_IDS), (
        f"{label}: expected {len(TAB_IDS)} section tabs, found {len(strip['tabs'])}"
    )
    # Nothing is scrolled out of sight inside the strip...
    assert strip["scrollWidth"] <= strip["clientWidth"] + 1, (
        f"{label}: tab strip hides {strip['scrollWidth'] - strip['clientWidth']}px "
        f"of tabs (overflow-x: {strip['overflowX']})"
    )
    # ...and no individual tab is clipped by the strip edges.
    clipped = [
        t["text"]
        for t in strip["tabs"]
        if t["left"] < strip["left"] - 1 or t["right"] > strip["right"] + 1
    ]
    assert not clipped, f"{label}: tabs clipped: {clipped}"
    # Wrapped rows stay inside the card (no vertical clipping either).
    assert strip["scrollHeight"] <= strip["clientHeight"] + 1, (
        f"{label}: tab strip clips its own wrapped rows"
    )
    # Touch targets and legibility.
    for tab in strip["tabs"]:
        assert tab["height"] >= 34, (
            f"{label}: tab '{tab['text']}' is only {tab['height']:.1f}px tall"
        )
        assert tab["fontSize"] >= 11, (
            f"{label}: tab '{tab['text']}' font is only {tab['fontSize']}px"
        )


# Fake-data helpers. Inputs are set through the DOM and dispatched as `input`
# events, which is exactly the path v-model listens to — fast for bulk content,
# and still the real binding path (typing is covered by the tests above).
MAX_OUT_JS = """(sel) => {
  const root = document.querySelector(sel);
  if (!root) return 0;
  let clicks = 0;
  root.querySelectorAll('button').forEach((btn) => {
    if (!btn.textContent.includes('+ Add') || btn.disabled) return;
    btn.click();
    clicks++;
  });
  return clicks;
}"""

FILL_PANE_JS = """(sel) => {
  const root = document.querySelector(sel);
  if (!root) return 0;
  const words = 'delivered migrated instrumented certified streamlined ' +
                'documented partnered automated measured improved ';
  let filled = 0;
  root.querySelectorAll('input[type="text"], textarea').forEach((el) => {
    if (el.disabled || el.readOnly) return;
    const limit = el.maxLength > 0 ? el.maxLength : 120;
    let text = '';
    while (text.length < limit) text += words;
    if (!text) return;
    el.value = text.slice(0, limit);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    filled++;
  });
  return filled;
}"""


def max_out_and_fill_pane(page, tab_id, pane_id):
    """Open a tab, click every '+ Add' until the limits bite, then fill it."""
    page.click(f"#{tab_id}")
    page.wait_for_timeout(150)
    for _ in range(6):
        if page.evaluate(MAX_OUT_JS, f"#{pane_id}") == 0:
            break
        page.wait_for_timeout(120)
    page.evaluate(FILL_PANE_JS, f"#{pane_id}")


def open_fullscreen(page):
    page.click(".preview-fullscreen-btn")
    page.wait_for_function(
        "() => document.querySelector('.resume-preview-container')"
        ".classList.contains('preview-fullscreen')",
        timeout=10000,
    )
    # Let the watcher's $nextTick -> fitPreview() land.
    page.wait_for_timeout(300)


def close_fullscreen(page):
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.querySelector('.resume-preview-container')"
        ".classList.contains('preview-fullscreen')",
        timeout=10000,
    )
    page.wait_for_timeout(200)


# ── The sheet always fits, and fills, its panel ────────────────────────────

@pytest.mark.e2e
class TestPreviewFitsItsPanel:
    @pytest.mark.parametrize("width,height,min_sheet_w", VIEWPORTS)
    def test_sheet_fills_the_panel_without_clipping(
        self, preview_page, width, height, min_sheet_w
    ):
        page = preview_page(width, height)
        g = geometry(page)

        # As large as the container allows — this is the whole point of
        # measuring instead of guessing per breakpoint.
        assert abs(g["sheetW"] - g["availW"]) <= 2, (
            f"sheet {g['sheetW']:.1f}px does not fill the {g['availW']:.1f}px "
            f"panel at {width}x{height} (scale {g['scale']})"
        )

        # Never clipped: both gaps are sane and nothing scrolls sideways.
        assert g["leftGap"] >= -1, f"sheet starts {g['leftGap']:.1f}px left of the panel"
        assert g["rightGap"] >= -1, f"sheet ends {g['rightGap']:.1f}px past the panel"
        assert g["wrapOverflowX"] <= 1, (
            f"preview scrolls horizontally by {g['wrapOverflowX']}px at {width}px"
        )
        assert g["docOverflowX"] <= 1, (
            f"page overflows horizontally by {g['docOverflowX']}px at {width}px"
        )

        # A4 proportions are preserved by the scale.
        assert abs(g["sheetH"] / g["sheetW"] - A4_H / A4_W) < 0.01

        # Readable size, not a thumbnail (the 254px-tablet regression).
        assert g["sheetW"] >= min_sheet_w, (
            f"sheet is only {g['sheetW']:.1f}px wide at {width}px — expected "
            f">= {min_sheet_w}px"
        )

        # Accessibility: the preview is a named landmark when not full screen.
        assert g["role"] == "region"
        assert g["ariaLabel"] == "Resume preview"
        assert not g["isFullscreen"]

    @pytest.mark.parametrize("device_name", DEVICE_PROFILES)
    def test_fits_real_device_profiles(
        self, preview_page, playwright, device_name, browser_name
    ):
        """One real profile per device class: DPR, touch, mobile UA, orientation.

        A viewport size alone proves nothing about a device — these run with the
        real descriptor, so DPR-driven rounding and the mobile UA are included.
        """
        if device_name not in playwright.devices:
            pytest.skip(f"{device_name} is not in this Playwright build")

        device = dict(playwright.devices[device_name])
        viewport = device.pop("viewport")
        device.pop("default_browser_type", None)
        if browser_name == "firefox":
            # Playwright cannot emulate a mobile viewport in Firefox; the size
            # matrix and the width sweep cover Firefox instead.
            device.pop("is_mobile", None)

        page = preview_page(viewport["width"], viewport["height"], **device)
        g = geometry(page)
        assert_sheet_fills_panel(
            g, f"{device_name} {viewport['width']}x{viewport['height']}"
        )

        # Full screen must work on a real profile too, and must cover exactly
        # the emulated viewport in both orientations.
        open_fullscreen(page)
        fs = geometry(page)
        assert fs["isFullscreen"]
        assert abs(fs["container"]["w"] - viewport["width"]) <= 1, (
            f"{device_name}: overlay is {fs['container']['w']:.0f}px wide, "
            f"viewport is {viewport['width']}px"
        )
        assert abs(fs["container"]["h"] - viewport["height"]) <= 1, (
            f"{device_name}: overlay is {fs['container']['h']:.0f}px tall, "
            f"viewport is {viewport['height']}px"
        )
        assert abs(fs["sheetW"] - fs["availW"]) <= 2
        close_fullscreen(page)

        # Closing full screen must restore the in-page geometry exactly.
        restored = geometry(page)
        assert not restored["isFullscreen"]
        assert abs(restored["sheetW"] - g["sheetW"]) <= 2, (
            f"{device_name}: sheet did not return to its in-page size"
        )

    def test_phone_stacks_preview_below_form(self, preview_page):
        page = preview_page(390, 844)
        positions = page.evaluate(
            """() => {
              const form = document.querySelector('#pills-tab').getBoundingClientRect();
              const cont = document.querySelector('.resume-preview-container')
                                     .getBoundingClientRect();
              return { formBottom: form.bottom, previewTop: cont.top,
                       previewLeft: cont.left, previewRight: cont.right };
            }"""
        )
        assert positions["previewTop"] > positions["formBottom"], (
            "on a phone the preview must sit below the form, not beside it"
        )
        assert positions["previewLeft"] >= -1
        assert positions["previewRight"] <= 391


# ── Every width, not just the breakpoints ──────────────────────────────────

@pytest.mark.e2e
class TestEveryResponsiveSize:
    """The sheet is measured, so it must be right at *any* width.

    Bootstrap only defines a handful of breakpoints; a user drags a window to
    every value in between. Sweeping one page through the whole range is much
    cheaper than 38 page loads and catches the awkward in-between widths where
    the old per-breakpoint scaling used to jump.
    """

    def test_width_sweep_keeps_sheet_fitted(self, preview_page):
        page = preview_page(1280, 900)
        failures = []
        for width in SIZE_SWEEP_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            try:
                wait_for_fit(page, timeout=4000)
                assert_sheet_fills_panel(geometry(page), f"width={width}px")
            except (AssertionError, PlaywrightTimeout) as exc:
                # Report every failing width, not just the first: a broken rule
                # usually spans a range and the range is the useful clue.
                failures.append(f"width={width}px: {str(exc).splitlines()[0]}")
        assert not failures, (
            f"{len(failures)} of {len(SIZE_SWEEP_WIDTHS)} widths failed:\n  "
            + "\n  ".join(failures)
        )

    def test_width_sweep_keeps_tabs_readable(self, preview_page):
        page = preview_page(1280, 900)
        failures = []
        for width in SIZE_SWEEP_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            try:
                wait_for_fit(page, timeout=4000)
                # The tab row is a reflow of its own; give the wrap a frame to land.
                page.wait_for_timeout(50)
                assert_tab_strip_readable(
                    page.evaluate(TAB_STRIP_JS), f"width={width}px"
                )
            except (AssertionError, PlaywrightTimeout) as exc:
                failures.append(f"width={width}px: {str(exc).splitlines()[0]}")
        assert not failures, (
            f"{len(failures)} of {len(SIZE_SWEEP_WIDTHS)} widths failed:\n  "
            + "\n  ".join(failures)
        )

    @pytest.mark.parametrize("width,height", SHORT_VIEWPORTS)
    def test_short_viewport_stays_usable(self, preview_page, width, height):
        """A short window must not collapse the panel or hide the controls."""
        page = preview_page(width, height)
        g = geometry(page)
        assert_sheet_fills_panel(g, f"{width}x{height}")

        assert g["container"]["h"] >= 100, (
            f"preview panel collapsed to {g['container']['h']:.0f}px at "
            f"{width}x{height}"
        )
        # The full screen button has to stay reachable at any height.
        box = page.locator(".preview-fullscreen-btn").bounding_box()
        assert box and box["height"] >= 30, f"toolbar button {box} at {width}x{height}"

        open_fullscreen(page)
        fs = geometry(page)
        assert abs(fs["container"]["h"] - height) <= 1, (
            f"overlay is {fs['container']['h']:.0f}px tall in a {height}px viewport"
        )
        assert abs(fs["sheetW"] - fs["availW"]) <= 2
        close_fullscreen(page)

    def test_orientation_flip_remeasures(self, preview_page):
        page = preview_page(390, 844)
        portrait = geometry(page)
        assert_sheet_fills_panel(portrait, "portrait 390x844")

        page.set_viewport_size({"width": 844, "height": 390})
        wait_for_fit(page)
        landscape = geometry(page)
        assert_sheet_fills_panel(landscape, "landscape 844x390")
        assert landscape["sheetW"] > portrait["sheetW"], (
            f"landscape gives {landscape['sheetW']:.0f}px, portrait "
            f"{portrait['sheetW']:.0f}px — the sheet should grow with the window"
        )

        page.set_viewport_size({"width": 390, "height": 844})
        wait_for_fit(page)
        again = geometry(page)
        assert abs(again["sheetW"] - portrait["sheetW"]) <= 2, (
            "rotating back to portrait did not restore the original scale"
        )


# ── The measurement follows the live container ─────────────────────────────

@pytest.mark.e2e
class TestPreviewFollowsLiveResize:
    def test_shrink_and_grow_remeasure(self, preview_page):
        page = preview_page(1440, 900)
        wide = geometry(page)
        assert abs(wide["sheetW"] - wide["availW"]) <= 2

        page.set_viewport_size({"width": 600, "height": 900})
        wait_for_fit(page)
        narrow = geometry(page)
        assert narrow["sheetW"] < wide["sheetW"] - 20, (
            "the sheet did not shrink with the panel: "
            f"{narrow['sheetW']:.1f} vs {wide['sheetW']:.1f}"
        )
        assert narrow["wrapOverflowX"] <= 1

        page.set_viewport_size({"width": 1600, "height": 900})
        wait_for_fit(page)
        grown = geometry(page)
        assert grown["sheetW"] > narrow["sheetW"] + 20, (
            "the sheet did not grow with the panel: "
            f"{grown['sheetW']:.1f} vs {narrow['sheetW']:.1f}"
        )
        assert abs(grown["sheetW"] - grown["availW"]) <= 2

    def test_orientation_change_remeasures(self, preview_page):
        page = preview_page(390, 844)
        portrait = geometry(page)
        page.set_viewport_size({"width": 844, "height": 390})
        wait_for_fit(page)
        landscape = geometry(page)
        assert landscape["sheetW"] > portrait["sheetW"], (
            "rotating to landscape did not widen the sheet"
        )
        assert abs(landscape["sheetW"] - landscape["availW"]) <= 2


# ── Full screen ────────────────────────────────────────────────────────────

@pytest.mark.e2e
class TestPreviewFullscreen:
    def test_overlay_covers_viewport_and_paints_above_chrome(self, preview_page):
        page = preview_page(1280, 800)
        panel = geometry(page)

        open_fullscreen(page)
        g = geometry(page)

        assert g["isFullscreen"]
        assert g["role"] == "dialog"
        assert g["ariaModal"] == "true"
        assert page.get_attribute(".preview-fullscreen-btn", "aria-pressed") == "true"

        vw = page.viewport_size["width"]
        vh = page.viewport_size["height"]
        box = g["container"]
        assert abs(box["x"]) <= 1 and abs(box["y"]) <= 1, f"overlay offset: {box}"
        assert abs(box["w"] - vw) <= 1, f"overlay width {box['w']} vs viewport {vw}"
        assert abs(box["h"] - vh) <= 1, f"overlay height {box['h']} vs viewport {vh}"

        # Full screen defaults to fit-width: strictly larger than the panel.
        assert g["sheetW"] > panel["sheetW"] + 100, (
            f"full screen sheet {g['sheetW']:.1f} is not larger than the panel "
            f"sheet {panel['sheetW']:.1f}"
        )
        assert abs(g["sheetW"] - g["availW"]) <= 2

        # Scrolling is locked while the overlay owns the screen.
        assert g["bodyOverflow"] == "hidden"
        assert g["htmlOverflow"] == "hidden"

        # Stacking regression guard: the navbar used to intercept clicks on the
        # overlay toolbar (flex-item stacking context at z-index 1020).
        hit = page.evaluate(
            """() => {
              const btn = document.querySelector('.preview-fitmode-btn');
              const r = btn.getBoundingClientRect();
              const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
              const overlay = document.querySelector(
                '.resume-preview-container.preview-fullscreen');
              return {
                inside: !!top && overlay.contains(top),
                tag: top ? top.tagName : null,
                cls: top ? String(top.className) : null,
              };
            }"""
        )
        assert hit["inside"], (
            "something paints above the full screen overlay at "
            f"({hit['tag']}.{hit['cls']}) — the toolbar is not clickable"
        )

    def test_escape_closes_and_restores_focus(self, preview_page):
        page = preview_page(1280, 800)
        panel = geometry(page)

        open_fullscreen(page)
        close_fullscreen(page)

        g = geometry(page)
        assert not g["isFullscreen"]
        assert g["role"] == "region"
        assert g["ariaModal"] is None
        assert page.get_attribute(".preview-fullscreen-btn", "aria-pressed") == "false"

        # Scroll lock released on both roots.
        assert g["bodyOverflow"] != "hidden"
        assert g["htmlOverflow"] != "hidden"

        # Back to the panel geometry exactly.
        assert abs(g["sheetW"] - panel["sheetW"]) <= 2
        assert abs(g["container"]["w"] - panel["container"]["w"]) <= 1

        focused = page.evaluate(
            "() => document.activeElement ? document.activeElement.className : ''"
        )
        assert "preview-fullscreen-btn" in focused, (
            f"focus was not returned to the full screen toggle (got '{focused}')"
        )

    def test_focus_trap_keeps_keyboard_inside_overlay(self, preview_page):
        page = preview_page(1280, 800)
        open_fullscreen(page)

        for _ in range(30):
            page.keyboard.press("Tab")
            inside = page.evaluate(
                """() => {
                  const box = document.querySelector(
                    '.resume-preview-container.preview-fullscreen');
                  return !!box && box.contains(document.activeElement);
                }"""
            )
            assert inside, "Tab escaped the full screen overlay"

    def test_fit_page_and_fit_width_modes(self, preview_page):
        page = preview_page(1280, 800)
        open_fullscreen(page)

        width_mode = geometry(page)
        assert width_mode["fitModeLabel"] == "Fit page", (
            "while fitted to width the button should offer 'Fit page', got "
            f"'{width_mode['fitModeLabel']}'"
        )
        assert abs(width_mode["sheetW"] - width_mode["availW"]) <= 2

        page.click(".preview-fitmode-btn")
        page.wait_for_timeout(350)
        page_mode = geometry(page)

        assert page_mode["fitModeLabel"] == "Fit width"
        # "Fit page" really fits the page: whole sheet inside the viewport.
        assert page_mode["sheetH"] <= page_mode["availH"] + 2, (
            f"fit-page sheet is {page_mode['sheetH']:.1f}px tall in a "
            f"{page_mode['availH']:.1f}px area"
        )
        # Measuring the sheet alone can agree with a stale scale; the scroll
        # extent cannot. Nothing may be clipped, so the wrapper must not scroll.
        assert page_mode["wrapOverflowY"] <= 0, (
            f"fit-page still needs {page_mode['wrapOverflowY']}px of vertical "
            "scrolling in the overlay"
        )
        assert page_mode["sheetW"] < width_mode["sheetW"], (
            "fit page should show the sheet smaller than fit width"
        )

        page.click(".preview-fitmode-btn")
        page.wait_for_timeout(350)
        assert abs(geometry(page)["sheetW"] - width_mode["sheetW"]) <= 2, (
            "toggling back to fit width did not restore the previous scale"
        )

    def test_fullscreen_available_on_phone(self, preview_page):
        page = preview_page(390, 844)
        open_fullscreen(page)
        g = geometry(page)

        assert g["isFullscreen"]
        assert abs(g["container"]["w"] - 390) <= 1
        assert abs(g["container"]["h"] - 844) <= 1
        assert g["sheetW"] > 340, f"phone full screen sheet is only {g['sheetW']:.1f}px"

        # The controls must remain reachable on a phone-sized overlay.
        for selector in (".preview-fitmode-btn", ".preview-fullscreen-btn"):
            box = page.locator(selector).bounding_box()
            assert box, f"{selector} is not rendered in full screen"
            assert box["height"] >= 30, f"{selector} is too small to tap: {box['height']}px"
            assert box["x"] >= 0 and box["x"] + box["width"] <= 391

        close_fullscreen(page)
        assert not geometry(page)["isFullscreen"]


# ── Section tab strip ──────────────────────────────────────────────────────

@pytest.mark.e2e
class TestSectionTabs:
    @pytest.mark.parametrize("width,height", TAB_VIEWPORTS)
    def test_no_tab_is_hidden_or_clipped(self, preview_page, width, height):
        page = preview_page(width, height)
        strip = page.evaluate(TAB_STRIP_JS)

        assert len(strip["tabs"]) == len(TAB_IDS), (
            f"expected {len(TAB_IDS)} section tabs, found {len(strip['tabs'])}"
        )
        assert [t["id"] for t in strip["tabs"]] == TAB_IDS

        assert_tab_strip_readable(strip, f"{width}x{height}")

        # Roving tabindex: exactly the selected tab is in the tab order.
        in_order = [t["id"] for t in strip["tabs"] if t["tabindex"] == 0]
        selected = [t["id"] for t in strip["tabs"] if t["selected"]]
        assert in_order == selected, (
            f"tabindex 0 belongs to {in_order} but aria-selected is {selected}"
        )

    @pytest.mark.parametrize("width,height", TAB_VIEWPORTS)
    def test_every_tab_switches_its_pane(self, preview_page, width, height):
        page = preview_page(width, height)

        for tab_id in TAB_IDS:
            page.click(f"#{tab_id}")
            pane_id = TAB_PANES[tab_id]
            page.wait_for_function(
                f"""() => {{
                  const pane = document.getElementById('{pane_id}');
                  return pane && pane.classList.contains('show') &&
                         getComputedStyle(pane).display !== 'none';
                }}""",
                timeout=5000,
            )
            states = page.evaluate(
                """(ids) => ids.map((id) => {
                     const el = document.getElementById(id);
                     return { id, selected: el.getAttribute('aria-selected') };
                   })""",
                TAB_IDS,
            )
            chosen = [s["id"] for s in states if s["selected"] == "true"]
            assert chosen == [tab_id], (
                f"after clicking {tab_id} the selected tabs were {chosen}"
            )

    def test_arrow_keys_move_between_tabs(self, preview_page):
        page = preview_page(1280, 800)
        page.focus("#pills-basics-tab")
        assert page.evaluate("() => document.activeElement.id") == "pills-basics-tab"

        page.keyboard.press("ArrowRight")
        assert page.evaluate("() => document.activeElement.id") == "pills-edu-tab"
        assert page.get_attribute("#pills-edu-tab", "aria-selected") == "true"

        page.keyboard.press("ArrowRight")
        assert page.evaluate("() => document.activeElement.id") == "pills-exp-tab"

        page.keyboard.press("ArrowLeft")
        assert page.evaluate("() => document.activeElement.id") == "pills-edu-tab"

        page.keyboard.press("End")
        assert page.evaluate("() => document.activeElement.id") == "pills-extra-tab"
        assert page.get_attribute("#pills-extra-tab", "aria-selected") == "true"

        page.keyboard.press("Home")
        assert page.evaluate("() => document.activeElement.id") == "pills-basics-tab"

        # Wrapping: Left from the first tab lands on the last one.
        page.keyboard.press("ArrowLeft")
        assert page.evaluate("() => document.activeElement.id") == "pills-extra-tab"

    def test_tab_away_leaves_the_tablist(self, preview_page):
        """With roving tabindex, Tab moves into the panel once, not 7 times."""
        page = preview_page(1280, 800)
        page.click("#pills-basics-tab")
        page.focus("#pills-basics-tab")
        page.keyboard.press("Tab")

        active = page.evaluate(
            """() => ({
                 id: document.activeElement.id,
                 inTablist: !!document.activeElement.closest('#pills-tab'),
               })"""
        )
        assert not active["inTablist"], (
            "Tab moved to another tab button instead of leaving the tablist"
        )
        assert active["id"] == "resume-name", (
            f"Tab should land on the first field of the active pane, got {active['id']}"
        )


# ── Live data: typed input reaches the sheet ───────────────────────────────

@pytest.mark.e2e
class TestLiveFakeData:
    def test_typed_values_appear_in_the_preview(self, preview_page):
        page = preview_page(1280, 800)

        page.fill("#resume-name", "Nurul Aisyah Rahman")
        page.fill("#resume-title", "Senior Platform Engineer")
        page.fill("#resume-email", "nurul.aisyah@fakemail.dev")
        page.fill("#resume-phone", "+60 19-882 4410")
        page.fill("#resume-location", "Penang, MY")
        page.fill(
            "#resume-summary",
            "Platform engineer focused on reliable delivery pipelines and "
            "developer experience for regulated financial systems.",
        )

        page.click("#pills-edu-tab")
        page.fill("#edu-school-0", "Universiti Sains Malaysia")
        page.fill("#edu-degree-0", "BSc (Hons) Software Engineering")

        page.click("#pills-exp-tab")
        page.fill("#exp-company-0", "Northwind Payments Sdn Bhd")
        page.fill("#exp-position-0", "Senior Platform Engineer")
        page.fill("#exp-date-0", "Mar 2023 - Present")
        page.locator("#tab-exp textarea").first.fill(
            "Cut deployment lead time from 45 to 6 minutes by rebuilding the "
            "release pipeline around reusable environment templates."
        )

        page.click("#pills-skills-tab")
        page.locator("#tab-skills input").first.fill("Kubernetes")

        page.click("#pills-others-tab")
        page.locator("#tab-others input").first.fill("CKA (Certified Kubernetes Administrator)")

        page.click("#pills-extra-tab")
        page.locator("#tab-extra input").first.fill("Open to relocation within ASEAN.")

        expected = [
            "Nurul Aisyah Rahman",
            "Senior Platform Engineer",
            "nurul.aisyah@fakemail.dev",
            "+60 19-882 4410",
            "Penang, MY",
            "reliable delivery pipelines",
            "Universiti Sains Malaysia",
            "BSc (Hons) Software Engineering",
            "Northwind Payments Sdn Bhd",
            "Cut deployment lead time",
            "Kubernetes",
            "CKA (Certified Kubernetes Administrator)",
            "Open to relocation within ASEAN.",
        ]
        page.wait_for_function(
            """(needles) => {
                const el = document.querySelector('#resume-template');
                if (!el) return false;
                // Themes upper-case parts of the sheet (name/title), so compare
                // case-insensitively instead of asserting the display casing.
                const text = el.innerText.toLowerCase();
                return needles.every((n) => text.includes(n.toLowerCase()));
            }""",
            arg=expected,
            timeout=10000,
        )

        # The sheet must not have changed size while filling it.
        g = geometry(page)
        assert abs(g["sheetW"] - g["availW"]) <= 2
        assert g["wrapOverflowX"] <= 1

    def test_unbroken_string_wraps_inside_the_sheet(self, preview_page):
        page = preview_page(1280, 800)
        before = geometry(page)

        # 120 characters with no break opportunity at all.
        page.fill("#resume-location", "A" * 30)
        page.fill("#resume-website", "https://" + "z" * 60 + ".example")
        page.fill(
            "#resume-summary",
            "Z" * 120 + " wrapped tail text for the summary field.",
        )
        page.fill("#resume-name", "Q" * 50)

        page.wait_for_timeout(500)
        after = geometry(page)

        assert abs(after["sheetW"] - before["sheetW"]) <= 1, (
            "long unbroken text resized the sheet "
            f"({before['sheetW']:.1f} -> {after['sheetW']:.1f})"
        )
        assert after["templateOverflowX"] <= 1, (
            "unbroken text overflows the sheet by "
            f"{after['templateOverflowX']}px instead of wrapping"
        )
        assert after["wrapOverflowX"] <= 1

    def test_multi_page_content_paginates_without_changing_zoom(self, preview_page):
        page = preview_page(1280, 800)
        zoom_before = geometry(page)["scale"]

        # Fill every section to its documented maximum with fake data. This is
        # the "dense resume" case: it must paginate correctly instead of
        # overflowing one sheet.
        for tab_id, pane_id in TAB_PANES.items():
            if pane_id == "tab-basics":
                page.click(f"#{tab_id}")
                page.evaluate(FILL_PANE_JS, "#tab-basics")
                continue
            max_out_and_fill_pane(page, tab_id, pane_id)

        page.wait_for_selector(".resume-pagination", timeout=15000)
        counter = page.locator(".page-counter").inner_text()
        assert "Page 1 /" in counter, f"unexpected page counter: {counter}"
        total = int(counter.split("/")[1].strip())
        assert total > 1, f"expected multiple pages for a full resume, got {counter}"

        page.click(".page-nav-btn:has-text('Next')")
        page.wait_for_timeout(300)

        g = geometry(page)
        assert "translateY(-297mm)" in g["templateTransform"], (
            f"second page offset missing from the sheet transform: "
            f"'{g['templateTransform']}'"
        )
        assert abs(g["scale"] - zoom_before) <= 0.0001, (
            "paging changed the zoom "
            f"({zoom_before} -> {g['scale']}); pagination must not rescale"
        )
        assert abs(g["sheetW"] - g["availW"]) <= 2
        assert g["wrapOverflowX"] <= 1

        # Back to page 1 and the sheet returns to its original offset.
        page.click(".page-nav-btn:has-text('Previous')")
        page.wait_for_timeout(300)
        back = geometry(page)
        assert "-297mm" not in back["templateTransform"], (
            f"returning to page 1 left the sheet offset: '{back['templateTransform']}'"
        )
