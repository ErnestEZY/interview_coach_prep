"""Accessibility: what a screen-reader or keyboard user actually receives.

axe-core is injected from the same CDN the application already loads Vue and
Bootstrap from, so this adds no dependency the app does not already have — a
page whose CDN is unreachable does not render at all.

Only the WCAG A and AA rule sets are requested. The rest of axe's catalogue is
advisory, and mixing it in buries real failures under style opinions.

Rules of impact "critical" and "serious" fail. "moderate" and "minor" are
attached to the failure message when something blocking is found, because a
rule that fires on every page is a product decision rather than a test
decision — but it is never silently dropped.
"""
import pytest
from pathlib import Path

import httpx

pytestmark = pytest.mark.e2e

AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
AXE_CACHE = Path(__file__).with_name(".vendor") / "axe-4.10.2.min.js"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
BLOCKING = ("critical", "serious")

PUBLIC_PAGES = [
    "/",
    "/static/pages/login.html",
    "/static/pages/register.html",
    "/static/pages/about.html",
    "/static/pages/privacy.html",
    "/static/pages/terms.html",
    "/static/pages/forgot_password.html",
    "/static/pages/reset_password.html",
    "/static/pages/verify.html",
]

AUTHED_PAGES = [
    "/static/pages/dashboard.html",
    "/static/pages/interview.html",
    "/static/pages/history.html",
    "/static/pages/resume_builder.html",
    "/static/pages/find-jobs.html",
]


@pytest.fixture(scope="session")
def axe_source():
    """axe-core, downloaded once per session and kept on disk.

    Injected by URL, every one of the fifteen audits was a separate chance for
    jsdelivr to stall: one bad fetch turned a 19-second suite into 37 minutes
    and reported it as a product failure. One download, then a local file.
    """
    if not AXE_CACHE.exists():
        AXE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = httpx.get(AXE_URL, timeout=30, follow_redirects=True)
            response.raise_for_status()
        except Exception as exc:
            pytest.skip(f"axe-core could not be fetched and is not cached: {exc}")
        AXE_CACHE.write_text(response.text, encoding="utf-8")
    return AXE_CACHE.read_text(encoding="utf-8")


def run_axe(page, source):
    """Every WCAG A/AA violation on the current document, with impact."""
    page.add_script_tag(content=source)
    page.wait_for_function("() => typeof axe !== 'undefined'", timeout=20000)
    return page.evaluate(
        """async (tags) => {
             const result = await axe.run(document, {
               runOnly: { type: 'tag', values: tags },
               resultTypes: ['violations'],
             });
             return result.violations.map((v) => ({
               id: v.id,
               impact: v.impact,
               help: v.help,
               count: v.nodes.length,
               nodes: v.nodes.slice(0, 4).map((n) => {
                 const data = (n.any && n.any[0] && n.any[0].data) || {};
                 return {
                   target: (n.target || []).join(' '),
                   fg: data.fgColor || null,
                   bg: data.bgColor || null,
                   ratio: data.contrastRatio || null,
                   need: data.expectedContrastRatio || null,
                 };
               }),
             }));
           }""",
        AXE_TAGS,
    )


def blocking(violations):
    return [v for v in violations if v["impact"] in BLOCKING]


def describe(violations):
    """One line per rule, with the offending selectors and, for contrast, the
    colour pair — so a failure says what to change instead of what to think."""
    lines = []
    for v in violations:
        lines.append(f"[{v['impact']}] {v['id']} x{v['count']}: {v['help']}")
        for n in v["nodes"]:
            detail = ""
            if n["ratio"]:
                detail = f" ({n['fg']} on {n['bg']} = {n['ratio']}, needs {n['need']})"
            lines.append(f"    {n['target']}{detail}")
    return "\n".join(lines)


def settle(page):
    """Wait until the page has stopped moving.

    Entry animations blend colours while they run, and axe reads the blended
    pixels as a contrast failure that is gone a moment later — measures that
    would otherwise make this suite report defects the user never sees.
    Infinite animations (spinners) are left alone: they are a deliberate state,
    not a transition that is about to finish.
    """
    page.wait_for_load_state("load")
    page.wait_for_function(
        """() => {
             const host = document.querySelector('#app');
             if (host && !host._vnode) return false;  // Vue has not rendered yet
             return document.getAnimations().every((a) => {
               if (a.playState !== 'running') return true;
               const timing = a.effect && a.effect.getComputedTiming
                 ? a.effect.getComputedTiming() : null;
               return !!timing && timing.iterations === Infinity;
             });
           }""",
        timeout=10000,
    )


def audit(page, path, source):
    page.goto(path)
    settle(page)
    violations = run_axe(page, source)
    found = blocking(violations)
    assert not found, (
        f"{path} has {len(found)} blocking accessibility violation(s):\n"
        + describe(found)
        + "\n\nAlso reported (not blocking):\n"
        + (describe([v for v in violations if v not in found]) or "none")
    )


class TestPublicPages:
    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_no_blocking_violations(self, page, base_url, axe_source, path):
        audit(page, f"{base_url}{path}", axe_source)


class TestAuthenticatedPages:
    @pytest.mark.parametrize("path", AUTHED_PAGES)
    def test_no_blocking_violations(self, authenticated_page, base_url, axe_source, path):
        audit(authenticated_page, f"{base_url}{path}", axe_source)


class TestDialogsAreNamed:
    """A dialog with no accessible name is announced as "dialog" and nothing
    else, which is the most common way a modal is unusable with a reader."""

    def test_analysis_overlay_is_named(self, authenticated_page, base_url, drive_vue):
        page = authenticated_page
        page.goto(f"{base_url}/static/pages/dashboard.html")
        page.wait_for_selector("#app", state="visible")
        assert drive_vue(page, showAnalysisProgress=True, analysisStatus="Analysing")

        overlay = page.locator(".analysis-progress-overlay")
        overlay.wait_for(state="visible")
        # role=dialog + aria-modal is not a name: a reader still needs a label
        # or a heading it can announce.
        heading = overlay.locator("h4").inner_text().strip()
        assert heading, "The analysis dialog has no heading to announce"
        assert overlay.get_attribute("aria-label") or overlay.get_attribute(
            "aria-labelledby"
        ), (
            "role=dialog without aria-label or aria-labelledby is announced as an "
            "unnamed dialog; the heading exists but is not linked to it"
        )
