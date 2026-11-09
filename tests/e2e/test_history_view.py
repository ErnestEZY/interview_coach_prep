"""
E2E Tests — Interview history: sorting, search, filtering and layout.

The history record only carries timestamps, a question count and a score, so
the search is asserted against exactly those, not against free text the data
cannot provide. Sessions are seeded directly into Mongo with fixed dates so the
orderings are deterministic regardless of what other runs have left behind;
assertions compare the relative order of the seeded ids instead of assuming the
account is empty.
"""
import os
import uuid

import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")
HISTORY_PATH = "/static/pages/history.html"
TEST_EMAIL = os.getenv("E2E_TEST_EMAIL", "e2e-test-user@playwright.dev")

# ── Seeded sessions ────────────────────────────────────────────────────────
# Dates are chosen so each ordering produces a different sequence, which is
# what makes the sort assertions meaningful.
SEEDED = [
    {"key": "old_55", "created": (2026, 1, 15, 10, 0), "ended": True, "score": 55, "asked": 5},
    {"key": "mar_88", "created": (2026, 3, 2, 9, 30), "ended": True, "score": 88, "asked": 8},
    {"key": "may_open", "created": (2026, 5, 20, 14, 15), "ended": False, "score": None, "asked": 2},
    {"key": "jun_72", "created": (2026, 6, 1, 8, 0), "ended": True, "score": 72, "asked": 10},
]

# What the DOM order should be for each sort, by SEEDED key.
EXPECTED_ORDER = {
    "desc": ["jun_72", "may_open", "mar_88", "old_55"],
    "asc": ["old_55", "mar_88", "may_open", "jun_72"],
    "score_desc": ["mar_88", "jun_72", "old_55", "may_open"],
    "score_asc": ["old_55", "jun_72", "mar_88", "may_open"],
}

LIST_JS = """() => {
  const cards = Array.from(document.querySelectorAll('#list [data-session-id]'));
  return cards.map((c) => {
    const text = c.innerText || '';
    // The score is rendered as "88/100" in the card body.
    const m = text.match(/(\\d{1,3})\\/100/);
    return { id: c.getAttribute('data-session-id'), score: m ? +m[1] : null, text };
  });
}"""


@pytest.fixture
def seeded_history(test_user_token):
    """Insert four sessions for the E2E user and remove them afterwards."""
    if not test_user_token:
        pytest.skip("No test user token — backend unreachable")

    from pymongo import MongoClient
    from backend.core.config import MONGO_URI, DB_NAME
    from datetime import datetime, timezone, timedelta

    if not MONGO_URI:
        pytest.skip("MONGO_URI not configured in the pytest process")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    inserted = {}
    try:
        db = client[DB_NAME]
        try:
            user = db["users"].find_one({"email": TEST_EMAIL})
        except Exception as exc:
            # A lookup that could not run is not the same finding as an account
            # that is missing, and reporting the first as the second sends the
            # reader looking for a seeding bug that does not exist.
            pytest.skip(f"could not read {DB_NAME} to seed history: {exc}")
        if not user:
            # Naming the database turns a missing-account report into a
            # mispointed-process report, which is the actual fault whenever the
            # app and this process disagree about which database to use.
            host = MONGO_URI.rsplit("@", 1)[-1].split("/")[0]
            pytest.skip(
                f"E2E user {TEST_EMAIL} is not in {DB_NAME} on {host} — the "
                f"pytest process and the running app must agree on the database"
            )

        user_id = str(user["_id"])
        # Malaysia is UTC+8 and has no DST, so a fixed offset is exact.
        myt = timezone(timedelta(hours=8))
        for spec in SEEDED:
            y, mo, d, h, mi = spec["created"]
            created = datetime(y, mo, d, h, mi, tzinfo=myt).astimezone(timezone.utc)
            doc = {
                "user_id": user_id,
                # session_id is uniquely indexed, so seeded rows must not share a
                # null value with each other.
                "session_id": f"e2e-history-{spec['key']}-{uuid.uuid4().hex[:10]}",
                "asked_count": spec["asked"],
                "created_at": created,
                "ended_at": created + timedelta(minutes=18) if spec["ended"] else None,
                "readiness_score": spec["score"],
                "readiness_breakdown": None,
                "readiness_feedback": "",
                "transcript": [],
                "questions_limit": 10,
                "test_seed": "test_history_view",
            }
            inserted[spec["key"]] = db["interviews"].insert_one(doc).inserted_id
        yield {k: str(v) for k, v in inserted.items()}
    finally:
        if inserted:
            client[DB_NAME]["interviews"].delete_many(
                {"_id": {"$in": list(inserted.values())}}
            )
        client.close()


@pytest.fixture
def history_page(browser, base_url, test_user_token):
    """Authenticated history page at a given viewport."""
    if not test_user_token:
        pytest.skip("No test user token — backend unreachable")

    contexts = []

    def open_page(width=1280, height=900):
        context = browser.new_context(viewport={"width": width, "height": height})
        context.add_init_script(
            f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
        )
        page = context.new_page()
        contexts.append(context)
        # A page whose script died still renders an empty list, so collect the
        # errors and report them instead of a bare timeout.
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )
        page.goto(f"{base_url}{HISTORY_PATH}")
        assert "/login.html" not in page.url, "history redirected to login — token rejected"
        page.wait_for_selector("#list", state="attached", timeout=30000)
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('#list [data-session-id]').length > 0",
                timeout=30000,
            )
        except Exception:
            detail = " | ".join(errors[:3]) or "no script error was reported"
            raise AssertionError(f"the history list never rendered: {detail}")
        return page

    yield open_page
    for context in contexts:
        context.close()


def visible(page):
    return page.evaluate(LIST_JS)


def order_of_seeded(page, seeded):
    """Seeded keys in DOM order, ignoring any sessions the account already had."""
    by_id = {v: k for k, v in seeded.items()}
    return [by_id[c["id"]] for c in visible(page) if c["id"] in by_id]


NEXT_PAINT_JS = """() => new Promise((done) => {
    requestAnimationFrame(() => requestAnimationFrame(done));
})"""


def settle(page):
    """Wait until the browser has painted the change that was just made.

    Sorting, searching and filtering are all applied in Vue, so the new list is
    produced in a microtask and painted in the next frame. A fixed sleep is a bet
    on how busy the machine is, and it lost that bet once: in a full-suite firefox
    run the unfiltered list was still on screen 250 ms after the status changed,
    and the test reported a filtering bug that did not exist. Two frames are the
    actual condition the sleep was standing in for.
    """
    page.evaluate(NEXT_PAINT_JS)


def choose_sort(page, value):
    page.select_option("#sortOrder", value)
    settle(page)


@pytest.mark.e2e
class TestHistorySorting:
    @pytest.mark.parametrize("sort_value", ["desc", "asc", "score_desc", "score_asc"])
    def test_sort_orders_the_list(self, history_page, seeded_history, sort_value):
        page = history_page()
        choose_sort(page, sort_value)
        assert order_of_seeded(page, seeded_history) == EXPECTED_ORDER[sort_value]

    def test_default_is_latest_first(self, history_page, seeded_history):
        page = history_page()
        assert order_of_seeded(page, seeded_history) == EXPECTED_ORDER["desc"]

    def test_toggling_back_restores_the_original_order(self, history_page, seeded_history):
        page = history_page()
        choose_sort(page, "asc")
        choose_sort(page, "desc")
        assert order_of_seeded(page, seeded_history) == EXPECTED_ORDER["desc"]

    def test_ungraded_sessions_sink_to_the_bottom_by_score(self, history_page, seeded_history):
        page = history_page()
        choose_sort(page, "score_desc")
        cards = visible(page)
        seeded_ids = set(seeded_history.values())
        seeded_cards = [c for c in cards if c["id"] in seeded_ids]
        # The in-progress session has no score and must never lead the list.
        assert seeded_cards[-1]["id"] == seeded_history["may_open"]
        assert seeded_cards[0]["score"] == 88


@pytest.mark.e2e
class TestHistorySearch:
    def test_search_by_score(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "88")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {seeded_history["mar_88"]}

    def test_search_by_status_word(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "completed")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {
            seeded_history["old_55"],
            seeded_history["mar_88"],
            seeded_history["jun_72"],
        }

    def test_search_by_iso_date(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "2026-03")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {seeded_history["mar_88"]}

    def test_search_by_month_name(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "jan")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {seeded_history["old_55"]}

    def test_search_is_case_insensitive(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "COMPLETED")
        settle(page)
        assert len(order_of_seeded(page, seeded_history)) == 3

    def test_session_id_is_not_searchable(self, history_page, seeded_history):
        """The id is an attribute on the card, never text on it.

        Keeping it in the search haystack meant a query could surface a card
        with nothing on it matching — and a plain "88" matched whichever
        session happened to carry those digits in its ObjectId, which made the
        score search above flake on one run in four.
        """
        page = history_page()
        page.fill("#history-search", seeded_history["mar_88"])
        settle(page)
        assert order_of_seeded(page, seeded_history) == []
        assert page.locator("#history-no-matches").count() == 1

    def test_no_match_shows_the_empty_filter_state(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "zzz-no-such-session")
        settle(page)
        assert page.locator("#history-no-matches").count() == 1
        assert visible(page) == []

    def test_clearing_the_search_restores_every_session(self, history_page, seeded_history):
        page = history_page()
        page.fill("#history-search", "88")
        settle(page)
        page.fill("#history-search", "")
        settle(page)
        assert len(order_of_seeded(page, seeded_history)) == 4


@pytest.mark.e2e
class TestHistoryStatusFilter:
    def test_in_progress_filter(self, history_page, seeded_history):
        page = history_page()
        page.select_option("#history-status", "inprogress")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {seeded_history["may_open"]}

    def test_completed_filter(self, history_page, seeded_history):
        page = history_page()
        page.select_option("#history-status", "completed")
        settle(page)
        assert len(order_of_seeded(page, seeded_history)) == 3

    def test_filter_and_search_combine(self, history_page, seeded_history):
        page = history_page()
        page.select_option("#history-status", "completed")
        page.fill("#history-search", "2026-06")
        settle(page)
        seeded_ids = set(seeded_history.values())
        found = {c["id"] for c in visible(page) if c["id"] in seeded_ids}
        assert found == {seeded_history["jun_72"]}

    def test_clear_filters_restores_the_full_list(self, history_page, seeded_history):
        page = history_page()
        page.select_option("#history-status", "inprogress")
        page.fill("#history-search", "88")
        settle(page)
        page.get_by_role("button", name="Clear filters").first.click()
        settle(page)
        assert len(order_of_seeded(page, seeded_history)) == 4
        assert page.input_value("#history-search") == ""
        assert page.input_value("#history-status") == "all"


@pytest.mark.e2e
class TestHistoryLayout:
    @pytest.mark.parametrize(
        "width,height",
        [
            pytest.param(320, 568, id="phone-320"),
            pytest.param(390, 844, id="phone-390"),
            pytest.param(768, 1024, id="tablet-768"),
            pytest.param(1280, 800, id="laptop-1280"),
            pytest.param(1920, 1080, id="wide-1920"),
        ],
    )
    def test_filters_fit_the_viewport(self, history_page, seeded_history, width, height):
        page = history_page(width, height)
        metrics = page.evaluate(
            """() => {
              const s = document.querySelector('#history-search').getBoundingClientRect();
              const st = document.querySelector('#history-status').getBoundingClientRect();
              const so = document.querySelector('#sortOrder').getBoundingClientRect();
              return {
                docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                searchW: s.width, searchRight: s.right,
                statusRight: st.right, sortRight: so.right,
                sortH: so.height, searchH: s.height,
                vw: window.innerWidth,
              };
            }"""
        )
        assert metrics["docOverflowX"] <= 1, (
            f"history page scrolls sideways by {metrics['docOverflowX']}px at {width}px"
        )
        assert metrics["searchW"] >= 120, (
            f"search box collapsed to {metrics['searchW']:.0f}px at {width}px"
        )
        for key in ("searchRight", "statusRight", "sortRight"):
            assert metrics[key] <= metrics["vw"] + 1, (
                f"{key} runs past the viewport at {width}px"
            )
        # Touch-friendly controls on phones.
        assert metrics["sortH"] >= 34
        assert metrics["searchH"] >= 34

    def test_filter_controls_are_labelled(self, history_page, seeded_history):
        page = history_page()
        # Each control needs a programmatic label (WCAG 1.3.1 / 4.1.2).
        assert page.locator("label[for='history-search']").count() == 1
        assert page.locator("label[for='history-status']").count() == 1
        assert page.locator("label[for='sortOrder']").count() == 1
        assert page.get_attribute("#history-search", "placeholder") != ""

    def test_sort_state_survives_an_interaction(self, history_page, seeded_history):
        page = history_page()
        choose_sort(page, "asc")
        page.fill("#history-search", "completed")
        settle(page)
        assert order_of_seeded(page, seeded_history) == [
            "old_55",
            "mar_88",
            "jun_72",
        ]


@pytest.mark.e2e
class TestHistoryPageIsHealthy:
    def test_renders_without_script_errors(
        self, browser, base_url, test_user_token, seeded_history
    ):
        """The page renders its own content: no script error, and no loading UI
        left over.

        The full-page loader this assertion used to check is gone — the list
        now owns its loading state — so it checks the state a user would
        actually be stuck with: a placeholder that never leaves, or an
        aria-busy that never clears.

        History once learned this the hard way: a global loader bound with v-if
        was detached by app.js instead of hidden, leaving Vue patching a node
        that was no longer in the document, and the list stayed empty for good.
        """
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            context.add_init_script(
                f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on(
                "console",
                lambda msg: errors.append(msg.text) if msg.type == "error" else None,
            )
            page.goto(f"{base_url}{HISTORY_PATH}")
            page.wait_for_selector("#list [data-session-id]", state="attached", timeout=30000)
            page.wait_for_timeout(800)

            assert errors == [], f"the page reported a script error: {errors[:3]}"
            # The list owns its own loading state now: once the rows are in, no
            # placeholder may be left behind pretending the fetch is still going.
            assert page.evaluate(
                """() => {
                  const list = document.querySelector('#list');
                  const placeholder = list.querySelector('.skeleton-surface');
                  return !placeholder && list.getAttribute('aria-busy') === 'false';
                }"""
            ), "the history list is still showing its loading placeholder"
        finally:
            context.close()


@pytest.mark.e2e
class TestHistoryLoadingState:
    """The list is the only thing on this page that is pure fetch output, which
    is what makes it the one surface here a placeholder can draw."""

    def test_skeleton_cards_hold_the_list_while_it_loads(
        self, browser, base_url, test_user_token, seeded_history
    ):
        """A request that never lands is the only way to see the placeholder.

        seeded_history is what the reload at the end has to land on: a fresh
        account has an empty list, and an empty list never shows the rows this
        test measures the placeholder against.

        Three things have to hold for the placeholder to be worth having: no
        rows while it is up (otherwise it is covering real content), it goes
        away when the rows arrive, and it is the size of the card it stands in
        for (otherwise the list jumps, which is the thing a skeleton exists to
        prevent) — plus it reveals late enough that a fast response never
        flashes it.
        """
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            context.add_init_script(
                f"try {{ localStorage.setItem('token', '{test_user_token}'); }} catch (e) {{ }}"
            )
            page = context.new_page()
            # Never continue: the request stays pending for as long as we need it.
            page.route("**/api/interview/history*", lambda route: None)
            page.goto(f"{base_url}{HISTORY_PATH}")

            page.wait_for_selector("#list .skeleton-surface", state="attached", timeout=15000)
            assert page.locator("#list [data-session-id]").count() == 0, (
                "rows were rendered before the history request finished"
            )
            assert page.get_attribute("#list", "aria-busy") == "true"
            # The reveal delay is the anti-flicker rule, not decoration: without
            # it a response inside 200ms paints a placeholder for a frame and the
            # page looks like it stuttered.
            delay = page.evaluate(
                """() => getComputedStyle(
                     document.querySelector('#list .skeleton-surface')).animationDelay"""
            )
            assert float(delay.rstrip("s")) >= 0.15, (
                f"the placeholder reveals after {delay}, soon enough to flash on a "
                f"fast response"
            )
            placeholder_h = page.evaluate(
                """() => Math.round(document
                     .querySelector('#list .skeleton-surface > .card')
                     .getBoundingClientRect().height)"""
            )

            page.unroute("**/api/interview/history*")
            page.reload()
            page.wait_for_selector("#list [data-session-id]", state="attached", timeout=30000)
            assert page.locator("#list .skeleton-surface").count() == 0, (
                "the placeholder survived the rows arriving"
            )
            assert page.get_attribute("#list", "aria-busy") == "false"

            # A placeholder that is a different size from the card it replaces
            # moves the whole list under the user's cursor when the data lands.
            # 12% leaves room for the engine's font metrics without allowing a
            # placeholder that is simply the wrong shape.
            card_h = page.evaluate(
                """() => Math.round(document
                     .querySelector('#list [data-session-id]')
                     .getBoundingClientRect().height)"""
            )
            drift = abs(placeholder_h - card_h) / card_h
            assert drift <= 0.12, (
                f"the placeholder is {placeholder_h}px tall but the card it stands "
                f"in for is {card_h}px — the list jumps by {abs(placeholder_h - card_h)}px "
                f"when the rows arrive"
            )
        finally:
            context.close()
