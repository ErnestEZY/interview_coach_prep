"""
E2E Tests — the resume preview shows the document, and the extracted text reads
like prose when it is asked for.

Two rules are asserted here:
  * the stored file is the preview (PDF frame / image), and the extracted text
    stays folded away behind a disclosure instead of standing in for it,
  * whatever text is shown has been reorganised into paragraphs and headings,
    with the letter-spaced output of glyph-by-glyph PDFs repaired.
"""
import os

import httpx
import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")
PORTAL_PATH = "/static/pages/icp-admin-portal-5e6a1c3d.html"
VIEWER_PATH = "/static/pages/icp-admin-view-2b8f4a10.html"
ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "e2e-admin@icp-solution.com")
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "E2eAdminPass123!")
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "ICP-SECURE-2026-ADMIN")

# Reads every rendered block and reports how readable it is. A line is called
# broken when most of its tokens are single characters, which is what
# "S o f t w a r e" looks like; readable prose never comes close.
MEASURE_BLOCKS = """
    (rootId) => {
      const root = document.getElementById(rootId);
      if (!root) return null;
      const blocks = Array.from(root.querySelectorAll('p, h6, li'))
        .map((el) => el.textContent.replace(/\\s+/g, ' ').trim())
        .filter(Boolean);
      const broken = blocks.filter((line) => {
        const tokens = line.split(' ').filter(Boolean);
        if (tokens.length < 6) return false;
        const singles = tokens.filter((t) => t.length === 1).length;
        return singles / tokens.length >= 0.6;
      });
      const lengths = blocks.map((line) => line.length);
      return {
        count: blocks.length,
        broken,
        totalChars: lengths.reduce((a, b) => a + b, 0),
        meanChars: lengths.length ? lengths.reduce((a, b) => a + b, 0) / lengths.length : 0,
        paragraphs: root.querySelectorAll('p').length,
        headings: root.querySelectorAll('h6').length,
        pre: document.querySelectorAll('pre').length,
      };
    }
"""


def admin_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_api_token():
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
def stored_pdfs(admin_api_token, seeded_resumes):
    """PDF submissions that still have their original file, newest first.

    seeded_resumes guarantees there is at least one, so the suite no longer
    skips on a database that happens to hold no uploads of its own.
    """
    r = httpx.get(
        f"{BASE_URL}/api/admin/resumes",
        params={"sort": "newest"},
        headers=admin_headers(admin_api_token),
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    pdfs = [
        item
        for item in r.json()
        if item.get("file_available")
        and (
            item.get("mime_type") == "application/pdf"
            or (item.get("filename") or "").lower().endswith(".pdf")
        )
    ]
    if not pdfs:
        pytest.skip("No stored PDF — nothing to preview")
    return pdfs


@pytest.fixture
def admin_page(browser, base_url, admin_user_token, seeded_resumes):
    if not admin_user_token:
        pytest.skip("No admin token — admin account not seeded")

    contexts = []

    def open_page(path, width=1280, height=900):
        context = browser.new_context(viewport={"width": width, "height": height})
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{admin_user_token}'); }} catch (e) {{ }}"
        )
        page = context.new_page()
        contexts.append(context)
        page.goto(f"{base_url}{path}")
        return page

    yield open_page
    for context in contexts:
        context.close()


@pytest.mark.e2e
class TestViewerShowsTheDocument:
    def test_the_document_is_the_preview_and_the_text_is_folded(
        self, admin_page, stored_pdfs
    ):
        page = admin_page(f"{VIEWER_PATH}?id={stored_pdfs[0]['id']}")
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)

        state = page.evaluate(
            """() => {
              const frame = document.querySelector('#resume-pdf-frame');
              const details = document.querySelector('#extracted-text');
              const notice = document.querySelector('#viewer-no-inline-preview');
              return {
                frameSrc: (frame.getAttribute('src') || '').slice(0, 5),
                frameH: frame.getBoundingClientRect().height,
                detailsOpen: details ? details.open : null,
                detailsPresent: !!details,
                noticeShown: !!notice,
              };
            }"""
        )
        assert state["frameSrc"] in ("http", "blob:"), (
            "the frame must point at the stored file"
        )
        assert state["frameH"] >= 240
        assert state["detailsPresent"], "the text fallback must still exist"
        assert state["detailsOpen"] is False, "the text must not stand in for the document"
        assert state["noticeShown"] is False, (
            "a PDF is renderable, so the cannot-preview notice must stay hidden"
        )

    def test_the_text_is_offered_on_demand(self, admin_page, stored_pdfs):
        page = admin_page(f"{VIEWER_PATH}?id={stored_pdfs[0]['id']}", 390, 844)
        page.wait_for_selector("#resume-pdf-frame", state="attached", timeout=25000)
        summary = page.locator("#extracted-text summary")
        assert summary.inner_text().strip().lower() == "extracted text"

        summary.click()
        page.wait_for_timeout(200)
        assert page.evaluate("() => document.querySelector('#extracted-text').open") is True
        assert page.locator("#extracted-text-body").is_visible()


@pytest.mark.e2e
class TestExtractedTextReadsLikeProse:
    def _blocks(self, page, root_id):
        return page.evaluate(MEASURE_BLOCKS, root_id)

    def test_viewer_text_is_laid_out_as_paragraphs(self, admin_page, stored_pdfs):
        page = admin_page(f"{VIEWER_PATH}?id={stored_pdfs[0]['id']}")
        page.wait_for_selector("#extracted-text-body p", state="attached", timeout=25000)

        m = self._blocks(page, "extracted-text-body")
        assert m["pre"] == 0, "raw preformatted text must be gone"
        assert m["count"] >= 5, f"only {m['count']} blocks were rendered"
        assert m["paragraphs"] >= 3
        assert m["headings"] >= 1, "section headings must be distinguished from prose"
        # One short line per paragraph is what the formatter must avoid.
        assert m["meanChars"] >= 40, f"mean block is only {m['meanChars']:.0f} chars"

    def test_no_block_is_letter_spaced_in_the_viewer(self, admin_page, stored_pdfs):
        page = admin_page(f"{VIEWER_PATH}?id={stored_pdfs[0]['id']}")
        page.wait_for_selector("#extracted-text-body p", state="attached", timeout=25000)

        m = self._blocks(page, "extracted-text-body")
        assert m["broken"] == [], (
            "letter-spaced extraction is still on screen: " + repr(m["broken"][:2])
        )

    def test_wrapped_lines_are_merged_into_paragraphs(self, admin_page, stored_pdfs):
        """The PDF wraps at ~90 chars; a merged paragraph is far longer."""
        page = admin_page(f"{VIEWER_PATH}?id={stored_pdfs[0]['id']}")
        page.wait_for_selector("#extracted-text-body p", state="attached", timeout=25000)

        longest = page.evaluate(
            """() => Math.max(...Array.from(
                  document.querySelectorAll('#extracted-text-body p')
                ).map((p) => p.textContent.trim().length), 0)"""
        )
        assert longest > 120, (
            f"the longest paragraph is {longest} chars, so wrapped lines were not merged"
        )


@pytest.mark.e2e
class TestPortalDetailPreview:
    def _open_first_detail(self, admin_page, width=1280, height=900):
        page = admin_page(PORTAL_PATH, width, height)
        page.wait_for_function(
            "() => document.querySelectorAll('#admin-resume-table tbody tr').length > 0",
            timeout=30000,
        )
        page.locator(
            "#admin-resume-table tbody tr button:has-text('Details')"
        ).first.click()
        page.wait_for_selector("#detail-preview-frame", state="attached", timeout=25000)
        page.wait_for_timeout(800)
        return page

    def test_the_panel_embeds_the_stored_file(self, admin_page):
        page = self._open_first_detail(admin_page)
        state = page.evaluate(
            """() => {
              const frame = document.querySelector('#detail-preview-frame');
              const link = document.querySelector('#detail-open-file');
              return {
                src: (frame.getAttribute('src') || '').slice(0, 5),
                height: frame.getBoundingClientRect().height,
                title: frame.getAttribute('title') || '',
                openHref: link ? (link.getAttribute('href') || '').slice(0, 5) : null,
                openTarget: link ? link.getAttribute('target') : null,
              };
            }"""
        )
        assert state["src"] == "blob:", (
            "the panel must render the fetched file, not link out for it"
        )
        assert state["height"] >= 200, f"panel preview is only {state['height']:.0f}px tall"
        assert "Resume preview" in state["title"]
        assert state["openHref"] == "blob:" and state["openTarget"] == "_blank"

    def test_the_panel_text_is_folded_and_readable(self, admin_page):
        page = self._open_first_detail(admin_page)
        state = page.evaluate(
            """() => {
              const details = document.querySelector('#detail-extracted-text');
              const body = document.querySelector('#detail-extracted-body');
              return {
                open: details.open,
                blocks: body.querySelectorAll('p, h6').length,
                pre: body.querySelectorAll('pre').length,
              };
            }"""
        )
        assert state["open"] is False, "the document is on screen, so text stays folded"
        assert state["pre"] == 0
        assert state["blocks"] >= 3

        page.locator("#detail-extracted-text summary").click()
        page.wait_for_timeout(250)
        m = page.evaluate(MEASURE_BLOCKS, "detail-extracted-body")
        assert m["broken"] == [], (
            "letter-spaced extraction is still in the admin panel: "
            + repr(m["broken"][:2])
        )
        assert m["meanChars"] >= 40

    def test_closing_the_panel_removes_the_embedded_file(self, admin_page):
        page = self._open_first_detail(admin_page)
        page.locator("button:has-text('Close')").first.click()
        page.wait_for_timeout(300)
        assert page.locator("#detail-preview-frame").count() == 0, (
            "the preview (and its object URL) must not outlive the panel"
        )
