"""Visual regression: the layout that DOM assertions cannot see.

An element can be present, correctly coloured and still wrong — shifted by a
missing margin, clipped by an overflow fix, or squeezed by a flex change. Those
are the defects a selector assertion passes and a user notices, so each surface
the design system is built from is pinned to a screenshot.

Baselines are per engine. Chromium, Firefox and WebKit rasterise text, shadows
and gradients differently, so one shared baseline would fail on two of the
three on every run and the suite would be ignored within a week.

They are also per host, because the application sets no text webfont: body copy
is drawn with the system font stack, so the same page screenshots differently
on Windows and on the Ubuntu CI runner. That is why this module is marked `vrt`
and CI runs the E2E suite with -m "not vrt" — a comparison here is only
meaningful against a baseline from the same host. Re-record before publishing
when a page changes on purpose.

The first run records a baseline and skips that case: a suite that silently
passes because it had nothing to compare against is worse than no suite.

    record or re-record:  $env:ICP_UPDATE_BASELINES = "1"; pytest tests/e2e/test_visual_regression.py
    compare:              pytest tests/e2e/test_visual_regression.py

A gate run must be the compare form. The switch survives in the shell it was
set in, and a recording run reports "recorded baseline" skips rather than
failures, so it looks like a quiet pass while having compared nothing; the
fixture below refuses to record when CI is set for that reason.
"""
import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

pytestmark = [pytest.mark.e2e, pytest.mark.vrt]

BASELINES = Path(__file__).with_name("__baselines__")
ARTIFACTS = Path(__file__).with_name("__baselines_artifacts__")


@pytest.fixture(scope="session", autouse=True)
def refuse_to_rebaseline_in_ci():
    """A CI run that re-records is a run that compared nothing, and passed.

    The record switch is inherited by every shell it was set in, which is how a
    gate can come back green having rewritten the baselines instead of checking
    them: six "recorded baseline" skips read like six ordinary skips. CI never
    records, so there the switch is an error rather than a mode.
    """
    if os.getenv("ICP_UPDATE_BASELINES") and os.getenv("CI"):
        pytest.fail(
            "ICP_UPDATE_BASELINES is set in CI. This run would rewrite every "
            "baseline and skip every comparison, then report success. Unset it."
        )


# A fixed viewport keeps the baseline independent of --viewport-size, so the
# same file means the same thing whoever runs it.
VIEWPORT = {"width": 1280, "height": 800}

# Antialiasing moves individual pixels without moving anything a user can see.
# A real regression moves far more than this, and a false failure here would
# cost more than the defect it is meant to catch.
MAX_DIFF_FRACTION = 0.002
CHANNEL_TOLERANCE = 12


def prepare(page, url):
    """Load a page and freeze everything that moves before capturing it."""
    page.set_viewport_size(VIEWPORT)
    page.emulate_media(reduced_motion="reduce")
    page.goto(url)
    page.add_style_tag(
        content="""
          *, *::before, *::after {
            animation: none !important;
            transition: none !important;
            caret-color: transparent !important;
          }
          #global-loader, .page-loader, .offline-overlay { display: none !important; }
        """
    )
    # Text metrics change when a webfont lands, which would move every line.
    page.wait_for_function("() => document.fonts.status === 'loaded'", timeout=20000)


def changed_pixels(actual, expected):
    """How many pixels differ by more than the channel tolerance."""
    diff = ImageChops.difference(actual, expected)
    red, green, blue = diff.split()
    worst = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = worst.point(lambda value: 255 if value > CHANNEL_TOLERANCE else 0)
    return mask.histogram()[255], mask


def assert_matches_baseline(name, engine, shot_bytes):
    baseline_dir = BASELINES / engine
    baseline = baseline_dir / f"{name}.png"

    if not baseline.exists() or os.getenv("ICP_UPDATE_BASELINES"):
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(shot_bytes)
        pytest.skip(f"recorded baseline {engine}/{name}.png")

    actual = Image.open(io.BytesIO(shot_bytes)).convert("RGB")
    expected = Image.open(baseline).convert("RGB")

    assert actual.size == expected.size, (
        f"{engine}/{name}.png is {expected.size[0]}x{expected.size[1]}, "
        f"the page now renders {actual.size[0]}x{actual.size[1]}"
    )

    changed, mask = changed_pixels(actual, expected)
    total = actual.size[0] * actual.size[1]
    share = changed / total
    if share <= MAX_DIFF_FRACTION:
        return

    out = ARTIFACTS / engine
    out.mkdir(parents=True, exist_ok=True)
    actual.save(out / f"{name}-actual.png")
    expected.save(out / f"{name}-expected.png")
    mask.save(out / f"{name}-difference.png")
    pytest.fail(
        f"{engine}/{name}.png: {changed} of {total} pixels differ "
        f"({share:.2%}, allowed {MAX_DIFF_FRACTION:.2%}).\n"
        f"Compare {out / (name + '-actual.png')} with "
        f"{out / (name + '-expected.png')}; the difference map is in the same folder."
    )


class TestPublicSurfaces:
    """Pages a visitor sees before they have an account."""

    def test_landing_nav(self, page, base_url, browser_name):
        prepare(page, f"{base_url}/")
        shot = page.locator("nav.glass-nav").screenshot()
        assert_matches_baseline("landing-nav", browser_name, shot)

    def test_login_card(self, page, base_url, browser_name):
        prepare(page, f"{base_url}/static/pages/login.html")
        shot = page.locator(".auth-card").screenshot()
        assert_matches_baseline("login-card", browser_name, shot)

    def test_register_card(self, page, base_url, browser_name):
        prepare(page, f"{base_url}/static/pages/register.html")
        shot = page.locator(".auth-card").screenshot()
        assert_matches_baseline("register-card", browser_name, shot)

    def test_forgot_password_card(self, page, base_url, browser_name):
        prepare(page, f"{base_url}/static/pages/forgot_password.html")
        shot = page.locator(".auth-card").screenshot()
        assert_matches_baseline("forgot-password-card", browser_name, shot)


class TestAuthenticatedSurfaces:
    """A component whose every state is code, not data: the analysis dialog."""

    def test_analysis_progress_dialog(self, authenticated_page, base_url, browser_name, drive_vue):
        page = authenticated_page
        prepare(page, f"{base_url}/static/pages/dashboard.html")
        assert drive_vue(
            page,
            showAnalysisProgress=True,
            analysisStatus="Analysing your resume…",
            analysisProgress=45,
            progressError=False,
        )
        card = page.locator(".analysis-progress-card")
        card.wait_for(state="visible")
        shot = card.screenshot()
        assert_matches_baseline("analysis-progress-card", browser_name, shot)

    def test_analysis_failure_dialog(self, authenticated_page, base_url, browser_name, drive_vue):
        """The failure state is a different colour, icon and copy — the state a
        CSS change is most likely to break without anyone noticing."""
        page = authenticated_page
        prepare(page, f"{base_url}/static/pages/dashboard.html")
        assert drive_vue(
            page,
            showAnalysisProgress=True,
            analysisStatus="Analysis could not complete.",
            analysisProgress=0,
            progressError=True,
        )
        card = page.locator(".analysis-progress-card")
        card.wait_for(state="visible")
        shot = card.screenshot()
        assert_matches_baseline("analysis-error-card", browser_name, shot)
