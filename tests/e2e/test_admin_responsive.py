"""
E2E Tests — Admin portal: responsive resume table and the candidate resume viewer.

Two things are asserted here that the existing admin tests did not cover:
  * the resume table stays readable on a phone instead of relying on sideways
    scrolling through six columns,
  * the date-created ordering is real (server-side) and the PDF viewer fills the
    viewport it is given, including a full screen mode.
"""
import os
from datetime import datetime

import httpx
import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")
PORTAL_PATH = "/static/pages/icp-admin-portal-5e6a1c3d.html"
VIEWER_PATH = "/static/pages/icp-admin-view-2b8f4a10.html"
ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "e2e-admin@icp-solution.com")
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "E2eAdminPass123!")
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "ICP-SECURE-2026-ADMIN")

DATE_FORMAT = "%m/%d/%Y, %I:%M:%S %p"


def admin_headers(token):
    return {"Authorization": f"Bearer {token}"}


def api_resumes(token, **params):
    r = httpx.get(
        f"{BASE_URL}/api/admin/resumes", params=params, headers=admin_headers(token), timeout=30
    )
    assert r.status_code == 200, r.text[:200]
    return r.json()


@pytest.fixture(scope="module")
def admin_api_token():
    """Module-scoped admin JWT taken straight from the API, independent of the UI."""
    r = httpx.post(
        f"{BASE_URL}/api/auth/admin_login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "invite_code": ADMIN_INVITE_CODE,
        },
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def pdf_resume_id(seeded_resumes):
    """The seeded submission that has a PDF behind it.

    Taken from the seeds rather than found by scanning the queue: a scan made
    the viewer suite depend on somebody else's submission having survived, and
    skip outright on a database that held none.
    """
    return seeded_resumes["pending_pdf"]


@pytest.fixture
def admin_page(browser, base_url, admin_user_token, seeded_resumes):
    """Authenticated admin page factory at a given viewport.

    seeded_resumes is requested for its setup, not its value: the queue has to
    hold rows before a test can assert anything about them.
    """
    if not admin_user_token:
        pytest.skip("No admin token — admin account not seeded")

    contexts = []

    def open_page(path, width=1280, height=900, wait_selector=None):
        context = browser.new_context(viewport={"width": width, "height": height})
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{admin_user_token}'); }} catch (e) {{ }}"
        )
        page = context.new_page()
        contexts.append(context)
        page.goto(f"{base_url}{path}")
        if wait_selector:
            page.wait_for_selector(wait_selector, state="attached", timeout=25000)
        return page

    yield open_page
    for context in contexts:
        context.close()


def open_portal(admin_page, width=1280, height=900):
    page = admin_page(PORTAL_PATH, width, height, wait_selector="#admin-resume-table")
    # tr[data-resume-id], not tr: the table renders skeleton rows while the
    # fetch is in flight, and those carry no id.
    page.wait_for_function(
        "() => document.querySelectorAll('#admin-resume-table tbody tr[data-resume-id]').length > 0",
        timeout=25000,
    )
    return page


def created_dates(page):
    return page.evaluate(
        """() => Array.from(
              document.querySelectorAll('#admin-resume-table tbody tr[data-resume-id]')
            ).map((tr) => tr.querySelector("td[data-label='Created (MYT)']").innerText.trim())"""
    )


@pytest.mark.e2e
class TestAdminResumeTableResponsive:
    @pytest.mark.parametrize(
        "width,height,expect_cards",
        [
            pytest.param(360, 800, True, id="phone-360"),
            pytest.param(390, 844, True, id="phone-390"),
            pytest.param(600, 900, True, id="small-tablet-600"),
            pytest.param(768, 1024, True, id="tablet-768"),
            pytest.param(1024, 1366, False, id="tablet-landscape-1024"),
            pytest.param(1280, 800, False, id="laptop-1280"),
            pytest.param(1920, 1080, False, id="wide-1920"),
        ],
    )
    def test_table_is_usable_without_sideways_scrolling(
        self, admin_page, width, height, expect_cards
    ):
        page = open_portal(admin_page, width, height)
        m = page.evaluate(
            """() => {
              const t = document.querySelector('#admin-resume-table');
              const thead = t.querySelector('thead');
              const row = t.querySelector('tbody tr[data-resume-id]');
              const td = row.querySelector('td');
              const before = getComputedStyle(td, '::before');
              return {
                docOverflowX: document.documentElement.scrollWidth
                  - document.documentElement.clientWidth,
                tableW: t.getBoundingClientRect().width,
                // clientWidth, not innerWidth: innerWidth counts a classic
                // scrollbar that the table cannot occupy, so the +1 tolerance
                // below would quietly allow that much clipping.
                viewportW: document.documentElement.clientWidth,
                theadDisplay: getComputedStyle(thead).display,
                rowDisplay: getComputedStyle(row).display,
                tdDisplay: getComputedStyle(td).display,
                labelContent: before.content,
                labelOpacity: before.display,
                rowCount: t.querySelectorAll('tbody tr[data-resume-id]').length,
              };
            }"""
        )
        assert m["docOverflowX"] <= 1, (
            f"admin page scrolls sideways by {m['docOverflowX']}px at {width}px"
        )
        assert m["tableW"] <= m["viewportW"] + 1
        assert m["rowCount"] > 0

        if expect_cards:
            # Rows become labelled blocks; the header row is redundant.
            assert m["theadDisplay"] == "none"
            assert m["rowDisplay"] == "block"
            assert m["tdDisplay"] == "flex"
            assert m["labelContent"] not in ("none", "normal", ""), (
                "stacked cells must name their field via data-label"
            )
        else:
            assert m["theadDisplay"] != "none"
            assert m["rowDisplay"] != "block"

    def test_every_stacked_cell_is_labelled(self, admin_page):
        page = open_portal(admin_page, 390, 844)
        labels = page.evaluate(
            """() => {
                  const row = document.querySelector(
                    '#admin-resume-table tbody tr[data-resume-id]');
                  return row
                    ? Array.from(row.querySelectorAll('td')).map((td) => td.getAttribute('data-label'))
                    : [];
                }"""
        )
        assert labels == ["Filename", "Status", "Tags", "Created (MYT)", "Notes", "Actions"]

    def test_pagination_and_filters_stay_in_the_viewport(self, admin_page):
        page = open_portal(admin_page, 360, 800)
        m = page.evaluate(
            """() => {
              const ids = ['admin-search', 'admin-status-filter', 'admin-tag-filter', 'admin-sort'];
              return ids.map((id) => {
                const r = document.getElementById(id).getBoundingClientRect();
                return { id, left: r.left, right: r.right };
              }).concat([{ id: 'vw', left: 0, right: window.innerWidth }]);
            }"""
        )
        vw = m[-1]["right"]
        for item in m[:-1]:
            assert item["left"] >= -1 and item["right"] <= vw + 1, (
                f"#{item['id']} is clipped at 360px"
            )


@pytest.mark.e2e
class TestAdminDateCreatedSort:
    def test_sort_control_offers_both_directions(self, admin_page):
        page = open_portal(admin_page)
        options = page.eval_on_selector_all(
            "#admin-sort option", "els => els.map(e => [e.value, e.textContent.trim()])"
        )
        assert [o[0] for o in options] == ["newest", "oldest"]
        assert "newest" in options[0][1].lower()
        assert "oldest" in options[1][1].lower()

    def test_newest_first_is_the_default_and_matches_the_api(self, admin_page, admin_api_token):
        page = open_portal(admin_page)
        assert page.input_value("#admin-sort") == "newest"

        dates = [datetime.strptime(d, DATE_FORMAT) for d in created_dates(page)]
        assert dates == sorted(dates, reverse=True), f"newest-first order broken: {dates}"

        api_ids = [r["id"] for r in api_resumes(admin_api_token, sort="newest")][:5]
        ui_ids = page.eval_on_selector_all(
            "#admin-resume-table tbody tr[data-resume-id]",
            "els => els.map(e => e.getAttribute('data-resume-id'))",
        )
        assert ui_ids == api_ids, (
            "the portal is not rendering the server's newest-first order"
        )

    def test_oldest_first_reverses_the_order(self, admin_page, admin_api_token):
        page = open_portal(admin_page)
        page.select_option("#admin-sort", "oldest")
        page.wait_for_timeout(1200)

        dates = [datetime.strptime(d, DATE_FORMAT) for d in created_dates(page)]
        assert dates == sorted(dates), f"oldest-first order broken: {dates}"

        api_ids = [r["id"] for r in api_resumes(admin_api_token, sort="oldest")][:5]
        ui_ids = page.eval_on_selector_all(
            "#admin-resume-table tbody tr[data-resume-id]",
            "els => els.map(e => e.getAttribute('data-resume-id'))",
        )
        assert ui_ids == api_ids, "oldest-first was not applied by the server query"

        api_dates = [
            r["created_at"] for r in api_resumes(admin_api_token, sort="oldest") if r.get("created_at")
        ]
        assert api_dates == sorted(api_dates), "server did not sort oldest first"

    def test_sort_is_sent_to_the_server(self, admin_page):
        page = open_portal(admin_page)
        requests = []
        page.on("request", lambda req: requests.append(req.url))
        page.select_option("#admin-sort", "oldest")
        page.wait_for_timeout(1200)
        assert any("sort=oldest" in url for url in requests), (
            f"no request carried sort=oldest (saw {requests[-3:]})"
        )

    def test_sort_label_explains_the_order(self, admin_page):
        page = open_portal(admin_page)
        page.select_option("#admin-sort", "oldest")
        page.wait_for_timeout(1000)
        assert "oldest first" in page.inner_text("body").lower()


@pytest.mark.e2e
class TestAdminResumeViewer:
    def test_viewer_frame_fills_its_width(self, admin_page, pdf_resume_id):
        for width, height in ((360, 800), (768, 1024), (1280, 800), (1920, 1080)):
            page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", width, height)
            page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
            page.wait_for_timeout(600)
            m = page.evaluate(
                """() => {
                  const f = document.querySelector('#resume-pdf-frame');
                  const s = document.querySelector('#admin-viewer-stage');
                  const shell = document.querySelector('.admin-viewer-shell');
                  const card = document.querySelector('.admin-viewer-shell > .card');
                  const fr = f.getBoundingClientRect(), sr = s.getBoundingClientRect();
                  return {
                    vw: window.innerWidth, vh: window.innerHeight,
                    // styles.css pins a scrollbar on <html>, so the width the
                    // layout actually gets is the body's, not innerWidth.
                    bw: document.body.getBoundingClientRect().width,
                    frameW: fr.width, frameH: fr.height,
                    stageW: sr.width, stageTop: sr.top,
                    cardW: card.getBoundingClientRect().width,
                    shellW: shell.getBoundingClientRect().width,
                    docOverflowX: document.documentElement.scrollWidth
                      - document.documentElement.clientWidth,
                    role: s.getAttribute('role'),
                    ariaLabel: s.getAttribute('aria-label'),
                  };
                }"""
            )
            assert m["docOverflowX"] <= 1, (
                f"viewer scrolls sideways at {width}px by {m['docOverflowX']}px"
            )
            assert abs(m["frameW"] - m["stageW"]) <= 1, "frame does not fill the stage width"
            # A frame that matches a too-narrow stage still passes the line
            # above, so the width has to be checked against its parents: the
            # stage must claim the card's content box and the card the
            # container's. This is what fails if the viewer shrinks to fit.
            assert m["stageW"] >= m["cardW"] - 40, (
                f"stage {m['stageW']:.0f}px fails to use card width {m['cardW']:.0f}px"
            )
            assert m["cardW"] >= m["shellW"] - 24, (
                f"card {m['cardW']:.0f}px fails to use container width {m['shellW']:.0f}px"
            )
            if width < 576:
                # Phones drop the container and card gutters so the sheet is
                # full bleed: only the card's 8px padding each side remains.
                assert m["frameW"] >= m["bw"] - 16.5, (
                    f"frame is only {m['frameW']:.0f}px wide in a {m['bw']:.0f}px body"
                )
            assert m["frameH"] >= 240, f"frame height {m['frameH']:.0f}px is unusable"
            assert m["role"] == "region"
            assert m["ariaLabel"]

    def test_open_in_new_tab_is_always_offered(self, admin_page, pdf_resume_id):
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 390, 844)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        link = page.locator("#open-file-new-tab")
        assert link.count() == 1
        assert link.get_attribute("target") == "_blank"
        assert link.get_attribute("rel") == "noopener"

    def test_open_file_action_is_offered_for_pdfs(self, admin_page, pdf_resume_id):
        """The original Open File action must live next to 'Open in new tab'.

        The embedded viewer paints a blank sheet in every headless engine, so
        the two are not duplicates: the plain link is the one an admin reaches
        for when the embed cannot render the PDF.
        """
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 1280, 800)
        page.wait_for_selector("#open-file-original", state="attached", timeout=25000)

        original = page.locator("#open-file-original")
        new_tab = page.locator("#open-file-new-tab")
        assert original.count() == 1 and new_tab.count() == 1
        assert "Open File" in original.inner_text()
        assert "Open in new tab" in new_tab.inner_text()
        # Same destination, so only the label tells them apart.
        assert original.get_attribute("href") == new_tab.get_attribute("href")
        assert original.get_attribute("target") == "_blank"
        assert original.get_attribute("rel") == "noopener"
        # Order in the toolbar, not on screen: the bar wraps on narrow widths.
        assert page.evaluate(
            """() => {
              const a = document.querySelector('#open-file-original');
              const b = document.querySelector('#open-file-new-tab');
              return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
            }"""
        ), "Open File must come before Open in new tab"

    def test_phone_view_states_the_fallback(self, admin_page, pdf_resume_id):
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 390, 844)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        hint = page.locator("#viewer-mobile-hint")
        assert hint.count() == 1 and hint.is_visible()

    def test_full_screen_covers_the_viewport_and_escape_restores(self, admin_page, pdf_resume_id):
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 1280, 800)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        page.wait_for_timeout(400)
        before = page.evaluate(
            "() => document.querySelector('#resume-pdf-frame').getBoundingClientRect().height"
        )

        button = page.locator("#toggle-viewer-fullscreen")
        assert button.get_attribute("aria-pressed") == "false"
        button.click()
        page.wait_for_function(
            "() => document.querySelector('#admin-viewer-stage')"
            ".classList.contains('admin-viewer-stage--fullscreen')",
            timeout=10000,
        )
        fs = page.evaluate(
            """() => {
              const s = document.querySelector('#admin-viewer-stage').getBoundingClientRect();
              const f = document.querySelector('#resume-pdf-frame').getBoundingClientRect();
              return {
                x: s.x, y: s.y, w: s.width, h: s.height,
                frameH: f.height,
                bodyOverflow: getComputedStyle(document.body).overflow,
                pressed: document.getElementById('toggle-viewer-fullscreen')
                  ? document.getElementById('toggle-viewer-fullscreen').getAttribute('aria-pressed')
                  : null,
                exitVisible: !!document.querySelector('.admin-viewer-exit'),
              };
            }"""
        )
        assert (fs["x"], fs["y"]) == (0, 0)
        assert abs(fs["w"] - 1280) <= 1 and abs(fs["h"] - 800) <= 1
        assert fs["frameH"] >= 799
        assert fs["bodyOverflow"] == "hidden", "background must not scroll in full screen"
        assert fs["exitVisible"]

        page.keyboard.press("Escape")
        page.wait_for_function(
            "() => !document.querySelector('#admin-viewer-stage')"
            ".classList.contains('admin-viewer-stage--fullscreen')",
            timeout=10000,
        )
        page.wait_for_timeout(300)
        after = page.evaluate(
            """() => ({
              overflow: getComputedStyle(document.body).overflow,
              focused: document.activeElement ? document.activeElement.id : null,
              frameH: document.querySelector('#resume-pdf-frame').getBoundingClientRect().height,
            })"""
        )
        assert after["overflow"] != "hidden"
        assert after["focused"] == "toggle-viewer-fullscreen", (
            "focus must return to the control that opened full screen"
        )
        assert abs(after["frameH"] - before) <= 2, "frame height not restored on exit"

    def test_full_screen_works_on_a_phone(self, admin_page, pdf_resume_id):
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 390, 844)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        page.locator("#toggle-viewer-fullscreen").click()
        page.wait_for_timeout(500)
        fs = page.evaluate(
            """() => {
              const s = document.querySelector('#admin-viewer-stage').getBoundingClientRect();
              const exit = document.querySelector('.admin-viewer-exit');
              const r = exit.getBoundingClientRect();
              return {
                w: s.width, h: s.height, vw: innerWidth, vh: innerHeight,
                exitLeft: r.left, exitRight: r.right,
                exitTop: r.top, exitBottom: r.bottom,
              };
            }"""
        )
        assert abs(fs["w"] - 390) <= 1 and abs(fs["h"] - 844) <= 1
        assert fs["exitLeft"] >= 0 and fs["exitRight"] <= fs["vw"] + 1, (
            "exit control must stay on screen"
        )
        assert fs["exitBottom"] <= fs["vh"] + 1
        assert fs["exitTop"] >= fs["vh"] / 2, (
            "the exit control must stay out of the reader's top toolbar"
        )

    def test_exit_control_clears_the_readers_own_toolbar(self, admin_page, pdf_resume_id):
        """Chrome, Firefox and Safari all draw their PDF toolbar across the top
        of the embedded frame — page selector on the left, zoom/download/print
        on the right. An exit control pinned to a top corner covers those
        buttons, so it lives along the bottom edge instead."""
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", 1280, 800)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        page.locator("#toggle-viewer-fullscreen").click()
        page.wait_for_timeout(500)
        box = page.evaluate(
            """() => {
              const r = document.querySelector('.admin-viewer-exit').getBoundingClientRect();
              return { top: r.top, bottom: r.bottom, left: r.left, right: r.right,
                       vw: innerWidth, vh: innerHeight };
            }"""
        )
        assert box["top"] >= box["vh"] / 2, (
            f"exit control sits at y={box['top']:.0f}, inside the reader toolbar band"
        )
        assert box["bottom"] <= box["vh"] + 1 and box["right"] <= box["vw"] + 1
        assert box["left"] >= 0

    @pytest.mark.parametrize(
        "width,height",
        [(360, 800), (390, 844), (576, 900), (768, 1024), (1280, 800)],
    )
    def test_toolbar_controls_never_overlap(self, admin_page, pdf_resume_id, width, height):
        """A wrapping toolbar must move buttons onto a new row, never stack
        them on top of each other."""
        page = admin_page(f"{VIEWER_PATH}?id={pdf_resume_id}", width, height)
        page.wait_for_selector("#toggle-viewer-fullscreen", state="attached", timeout=25000)
        # Both file links are only rendered once the blob URL exists, so waiting
        # for the last button alone can measure a half-built toolbar.
        page.wait_for_selector("#open-file-original", state="attached", timeout=25000)
        page.wait_for_selector("#open-file-new-tab", state="attached", timeout=25000)
        page.wait_for_timeout(400)
        m = page.evaluate(
            """() => {
              const ids = ['open-file-original', 'open-file-new-tab', 'toggle-viewer-fullscreen'];
              const boxes = ids.map((id) => {
                const el = document.getElementById(id);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { id, left: r.left, top: r.top, right: r.right, bottom: r.bottom };
              }).filter(Boolean);
              const overlaps = [];
              for (let i = 0; i < boxes.length; i += 1) {
                for (let j = i + 1; j < boxes.length; j += 1) {
                  const a = boxes[i], b = boxes[j];
                  const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
                  const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
                  if (ox > 0.5 && oy > 0.5) overlaps.push([a.id, b.id]);
                }
              }
              return {
                count: boxes.length,
                overlaps,
                docOverflowX: document.documentElement.scrollWidth
                  - document.documentElement.clientWidth,
                widestRight: Math.max(...boxes.map((b) => b.right)),
                // clientWidth excludes the classic scrollbar, which no control
                // may sit under; see the note in the table test above.
                vw: document.documentElement.clientWidth,
              };
            }"""
        )
        assert m["count"] == 3, "the toolbar lost a control while wrapping"
        assert m["overlaps"] == [], f"toolbar controls overlap: {m['overlaps']}"
        assert m["docOverflowX"] <= 1
        assert m["widestRight"] <= m["vw"] + 1
