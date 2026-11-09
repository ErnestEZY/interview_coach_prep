"""
E2E Tests — what an administrator is offered on the public pages.

The rules these pages have to satisfy:

  * an administrator who lands on the home or about page is routed back to the
    portal and never into the candidate dashboard — and the dashboard refuses
    them itself, including when the URL is typed or reached from a stale
    bookmark;
  * the account dropdown is a home-page affordance only: on the about page a
    signed-in visitor is shown just the route they came for;
  * on the home page the route badge sits beside the logo while the account
    menu ends the bar on the right, for both roles, and the account menu stays
    on screen when it opens;
  * the reflex chip is offered only on the home page and only to a signed-in
    visitor, and it closes the bar on the right, outside the account menu; it is
    an invitation rather than a scoreboard, so the speed only ever appears in
    its dialog and the best belongs to the account that set it;
  * a normal candidate keeps both the call-to-action and the account dropdown,
    so the rule cannot be satisfied by taking them away from everybody.

Links are sampled every 40 ms while the page settles: reading once would miss a
flash where the guest state renders a control before the role is known.
"""
import base64
import json

import pytest

PORTAL_PATH = "/static/pages/icp-admin-portal-5e6a1c3d.html"
DASHBOARD_PATH = "/static/pages/dashboard.html"
ABOUT_PATH = "/static/pages/about.html"

USER_CTA = "Go to Dashboard"
# The home page bar is short, so its label only names the portal; the about
# page has room for the fuller wording.
ADMIN_CTA = "Back to Portal"
ADMIN_ABOUT_CTA = "Back to Admin Portal"


def reflex_key(token):
    """The per-account storage key, derived the way the page derives it: from
    the account id in the token's subject."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return "icp_reflex_best:" + json.loads(base64.urlsafe_b64decode(payload))["sub"]


@pytest.fixture
def open_page(browser, base_url):
    """Factory for a token-seeded page; every context is closed afterwards.

    `storage` seeds any extra localStorage entries before the first script runs,
    which is how a stored personal best is put in place for the reflex chip.
    """
    contexts = []

    def _open(token, path="/", storage=None):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        seed = f"try {{ localStorage.setItem('token', '{token}'); }} catch (e) {{ }}"
        for key, value in (storage or {}).items():
            seed += f"try {{ localStorage.setItem({key!r}, {value!r}); }} catch (e) {{ }}"
        context.add_init_script(seed)
        page = context.new_page()
        contexts.append(context)
        page.goto(f"{base_url}{path}")
        return page

    yield _open
    for context in contexts:
        context.close()


@pytest.fixture
def admin_open(open_page, admin_user_token):
    if not admin_user_token:
        pytest.skip("No admin token — the E2E admin account could not be seeded")
    return lambda path="/", storage=None: open_page(admin_user_token, path, storage)


@pytest.fixture
def user_open(open_page, test_user_token):
    if not test_user_token:
        pytest.skip("No test user token — backend down or registration failed")
    return lambda path="/", storage=None: open_page(test_user_token, path, storage)


@pytest.fixture
def guest_open(browser, base_url):
    """A visitor with no token at all: the signed-in controls must not exist."""
    contexts = []

    def _open(path="/"):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        contexts.append(context)
        page.goto(f"{base_url}{path}")
        return page

    yield _open
    for context in contexts:
        context.close()


def observe(page, selector, ms=2500):
    """Sample the call-to-action, the account menu and every route on the page."""
    return page.evaluate(
        """async ({selector, ms}) => {
          const ctaTexts = new Set();
          const ctaHrefs = new Set();
          const dashboardHrefs = new Set();
          const adminHrefs = new Set();
          let accountMenus = 0;
          const deadline = Date.now() + ms;
          while (Date.now() < deadline) {
            const cta = document.querySelector(selector);
            if (cta) {
              ctaTexts.add((cta.innerText || '').replace(/\\s+/g, ' ').trim());
              ctaHrefs.add(cta.getAttribute('href') || '');
            }
            document.querySelectorAll('a[href]').forEach((a) => {
              const href = a.getAttribute('href') || '';
              if (href.includes('dashboard.html')) dashboardHrefs.add(href);
              if (href.includes('icp-admin-')) adminHrefs.add(href);
            });
            accountMenus = Math.max(
              accountMenus,
              document.querySelectorAll('.navbar .dropdown-toggle').length
            );
            await new Promise((resolve) => setTimeout(resolve, 40));
          }
          return {
            ctaTexts: Array.from(ctaTexts).filter(Boolean),
            ctaHrefs: Array.from(ctaHrefs).filter(Boolean),
            dashboardHrefs: Array.from(dashboardHrefs),
            adminHrefs: Array.from(adminHrefs),
            accountMenus,
          };
        }""",
        {"selector": selector, "ms": ms},
    )


def wait_for_nav(page):
    """Wait until the signed-in controls have been rendered, not before."""
    page.wait_for_selector("#app:not([v-cloak])", state="attached", timeout=25000)
    page.wait_for_selector("#home-nav-cta", state="attached", timeout=25000)
    page.wait_for_timeout(300)


# Where the brand, the two right-hand controls and the bar's own edges sit.
MEASURE_BAR = """() => {
  const container = document.querySelector('.navbar .container');
  const bar = container.getBoundingClientRect();
  const brand = document.querySelector('.navbar-brand').getBoundingClientRect();
  const toggle = document.querySelector('.navbar .dropdown-toggle').getBoundingClientRect();
  const cta = document.querySelector('#home-nav-cta');
  const reflex = document.querySelector('#home-reflex');
  return {
    barLeft: bar.left, barRight: bar.right,
    // The controls line up with the container's content box, which sits
    // inside its own gutter.
    barContentRight: bar.right - parseFloat(getComputedStyle(container).paddingRight),
    barContentLeft: bar.left + parseFloat(getComputedStyle(container).paddingLeft),
    brandLeft: brand.left, brandRight: brand.right,
    toggleLeft: toggle.left, toggleRight: toggle.right,
    ctaLeft: cta ? cta.getBoundingClientRect().left : null,
    reflexLeft: reflex ? reflex.getBoundingClientRect().left : null,
    reflexRight: reflex ? reflex.getBoundingClientRect().right : null,
  };
}"""


@pytest.mark.e2e
class TestAdminIsRoutedBackToThePortal:
    def test_home_offers_the_portal_and_not_the_dashboard(self, admin_open):
        seen = observe(admin_open("/"), "#home-primary-cta")
        assert set(seen["ctaTexts"]) == {ADMIN_CTA}, (
            f"admin call-to-action reads {seen['ctaTexts']}, expected {ADMIN_CTA}"
        )
        assert seen["ctaHrefs"] == [PORTAL_PATH], (
            f"admin call-to-action points at {seen['ctaHrefs']}"
        )
        assert seen["dashboardHrefs"] == [], (
            f"home page links an admin to the candidate dashboard: {seen['dashboardHrefs']}"
        )

    def test_home_keeps_the_account_menu(self, admin_open):
        """The dropdown is the one admin affordance the home page keeps."""
        page = admin_open("/")
        wait_for_nav(page)
        assert page.locator(".navbar .dropdown-toggle").count() == 1
        assert ADMIN_CTA in page.inner_text("#home-nav-cta")

    def test_about_offers_the_portal_without_an_account_menu(self, admin_open):
        seen = observe(admin_open(ABOUT_PATH), "#about-primary-cta")
        assert set(seen["ctaTexts"]) == {ADMIN_ABOUT_CTA}
        assert seen["ctaHrefs"] == [PORTAL_PATH]
        assert seen["accountMenus"] == 0, (
            "the account dropdown is a home-page affordance only"
        )
        assert seen["dashboardHrefs"] == []

    def test_dashboard_bounces_an_admin_to_the_portal(self, admin_open):
        """The guard has to work on the page itself, not only on the links to
        it: a bookmark or a typed URL never passes through the home page."""
        page = admin_open(DASHBOARD_PATH)
        page.wait_for_url(lambda url: PORTAL_PATH in url, timeout=25000)
        assert DASHBOARD_PATH not in page.url


@pytest.mark.e2e
class TestHomeBarArrangement:
    """One bar for both roles: the route badge sits beside the logo, and the
    controls a signed-in visitor acts with end the bar on the right — so the
    page does not move around depending on who is signed in."""

    def test_admin_badge_sits_beside_the_brand(self, admin_open):
        self._assert_badge_beside_the_brand(admin_open("/"))

    def test_candidate_badge_sits_beside_the_brand(self, user_open):
        self._assert_badge_beside_the_brand(user_open("/"))

    @staticmethod
    def _assert_badge_beside_the_brand(page):
        wait_for_nav(page)
        m = page.evaluate(MEASURE_BAR)
        assert m["brandLeft"] - m["barContentLeft"] < 4, "the brand must stay on the left"
        assert m["ctaLeft"] - m["brandRight"] < 40, (
            f"the badge sits {m['ctaLeft'] - m['brandRight']:.0f}px away from the brand"
        )

    def test_admin_controls_close_the_bar(self, admin_open):
        self._assert_controls_close_the_bar(admin_open("/"))

    def test_candidate_controls_close_the_bar(self, user_open):
        self._assert_controls_close_the_bar(user_open("/"))

    @staticmethod
    def _assert_controls_close_the_bar(page):
        wait_for_nav(page)
        m = page.evaluate(MEASURE_BAR)
        # The reflex chip ends the bar and the account menu sits just inside it,
        # in that order, for both roles.
        shortfall = m["barContentRight"] - m["reflexRight"]
        assert abs(shortfall) <= 2, (
            f"the reflex chip ends {shortfall:.0f}px short of the bar's right edge"
        )
        gap = m["reflexLeft"] - m["toggleRight"]
        assert gap >= -1, f"the account menu overlaps the reflex chip by {-gap:.0f}px"
        assert gap < 40, f"the account menu sits {gap:.0f}px away from the reflex chip"
        midpoint = (m["barLeft"] + m["barRight"]) / 2
        assert m["toggleLeft"] > midpoint, (
            "the account menu drifted back towards the middle of the bar"
        )

    def test_the_account_menu_stays_on_screen(self, admin_open):
        self._assert_menu_stays_on_screen(admin_open("/"))

    def test_a_candidates_account_menu_stays_on_screen(self, user_open):
        self._assert_menu_stays_on_screen(user_open("/"))

    @staticmethod
    def _assert_menu_stays_on_screen(page):
        wait_for_nav(page)
        page.locator(".navbar .dropdown-toggle").click()
        page.wait_for_selector(".navbar .dropdown-menu.show", timeout=10000)

        m = page.evaluate(
            """() => {
              const menu = document.querySelector('.navbar .dropdown-menu.show');
              const r = menu.getBoundingClientRect();
              return {
                menuLeft: r.left, menuRight: r.right, vw: window.innerWidth,
                endAligned: menu.classList.contains('dropdown-menu-end'),
              };
            }"""
        )
        assert m["endAligned"], "the menu must be anchored to the right of its trigger"
        assert m["menuLeft"] >= 0 and m["menuRight"] <= m["vw"] + 1, (
            f"the menu opens off screen: {m['menuLeft']:.0f}–{m['menuRight']:.0f}"
        )


@pytest.mark.e2e
class TestHomePageReflex:
    """The reflex chip is the home page's one playful control, and it belongs to
    neither role: an administrator and a candidate get the same easter egg. The
    personal best is the visitor's own — one scoreboard per account."""

    @staticmethod
    def run_once(page):
        """Play a round and return what the dialog told the visitor."""
        page.locator("#home-reflex").click()
        page.wait_for_selector("#reflex-target[data-state='go']", timeout=15000)
        page.locator("#reflex-target").click()
        return page.inner_text("#reflex-result")

    @staticmethod
    def stored(page, key):
        return page.evaluate("(key) => localStorage.getItem(key)", key)

    def test_a_candidate_is_offered_the_reflex_check(self, user_open):
        page = user_open("/")
        wait_for_nav(page)
        chip = page.locator("#home-reflex")
        assert chip.count() == 1, "a signed-in candidate has no reflex chip"
        assert chip.is_visible()
        assert (chip.get_attribute("aria-label") or "").strip(), (
            "the reflex check needs a spoken name for a screen reader"
        )

    def test_an_admin_is_offered_the_reflex_check(self, admin_open):
        page = admin_open("/")
        wait_for_nav(page)
        assert page.locator("#home-reflex").count() == 1, (
            "a signed-in admin has no reflex chip"
        )

    def test_the_chip_sits_outside_the_account_menu(self, user_open):
        page = user_open("/")
        wait_for_nav(page)
        m = page.evaluate(MEASURE_BAR)
        assert m["toggleRight"] <= m["reflexLeft"] + 1, (
            "the reflex chip is not to the right of the account menu"
        )

    def test_a_guest_is_not_offered_the_reflex_check(self, guest_open):
        page = guest_open("/")
        page.wait_for_selector("#app:not([v-cloak])", state="attached", timeout=25000)
        page.wait_for_timeout(800)
        assert page.locator("#home-reflex").count() == 0, (
            "the reflex check is offered to a visitor who is not signed in"
        )

    def test_the_reflex_check_is_not_on_other_pages(self, user_open):
        page = user_open(ABOUT_PATH)
        page.wait_for_selector("#app:not([v-cloak])", state="attached", timeout=25000)
        page.wait_for_timeout(800)
        assert page.locator("#home-reflex").count() == 0, (
            "the reflex check escaped the home page"
        )

    def test_the_chip_is_an_invitation_not_a_scoreboard(self, user_open, test_user_token):
        """A stored best must not leak onto the bar: the chip always reads the
        same, and the number belongs to the dialog alone."""
        page = user_open("/", storage={reflex_key(test_user_token): "180"})
        wait_for_nav(page)
        label = page.inner_text("#home-reflex").strip()
        assert label == "Reflex", f"the chip stopped being an invitation: {label!r}"
        aria = (page.locator("#home-reflex").get_attribute("aria-label") or "").strip()
        assert "180" not in aria, f"the chip advertises the personal best: {aria!r}"

    def test_a_stored_best_is_reported_in_the_dialog(self, user_open, test_user_token):
        """The one place a speed is allowed to appear: the dialog."""
        page = user_open("/", storage={reflex_key(test_user_token): "1"})
        wait_for_nav(page)
        result = self.run_once(page)
        assert "Personal best stays at 1 ms" in result, (
            f"the dialog did not name the best: {result!r}"
        )
        assert page.inner_text("#home-reflex").strip() == "Reflex", (
            "the run wrote a speed onto the chip"
        )

    def test_a_clean_run_records_a_personal_best(self, user_open, test_user_token):
        page = user_open("/")
        wait_for_nav(page)
        page.locator("#home-reflex").click()
        page.wait_for_selector(".swal2-popup", timeout=15000)

        target = page.locator("#reflex-target")
        target.wait_for(state="attached", timeout=10000)
        assert target.get_attribute("data-state") == "waiting", (
            "the panel was green before the visitor could have reacted"
        )
        page.wait_for_selector("#reflex-target[data-state='go']", timeout=15000)
        target.click()

        assert "New personal best" in page.inner_text("#reflex-result"), (
            f"the first run was not celebrated: {page.inner_text('#reflex-result')!r}"
        )
        saved = self.stored(page, reflex_key(test_user_token))
        assert saved and int(saved) > 0, f"the personal best was not stored: {saved!r}"
        legacy = page.evaluate("() => localStorage.getItem('icp_reflex_best')")
        assert not legacy, f"the best was written to the shared key: {legacy!r}"
        assert page.inner_text("#home-reflex").strip() == "Reflex", (
            "the new personal best was written onto the chip"
        )

    def test_clicking_before_the_green_is_caught(self, user_open, test_user_token):
        page = user_open("/")
        wait_for_nav(page)
        page.locator("#home-reflex").click()
        page.wait_for_selector(".swal2-popup", timeout=15000)

        target = page.locator("#reflex-target")
        target.wait_for(state="attached", timeout=10000)
        assert target.get_attribute("data-state") == "waiting", (
            "the panel was green before the visitor could have reacted"
        )
        target.click()

        assert target.get_attribute("data-state") == "early", (
            "an early click was scored as a reaction rather than caught"
        )
        assert "Anticipation" in page.inner_text("#reflex-result")
        saved = self.stored(page, reflex_key(test_user_token))
        assert not saved, f"an early click recorded a personal best: {saved!r}"

    def test_each_account_keeps_its_own_best(
        self, browser, base_url, test_user_token, admin_user_token
    ):
        """One browser profile, two people: the second one signs in on the same
        machine and must not inherit the first one's scoreboard."""
        if not test_user_token or not admin_user_token:
            pytest.skip("Both accounts are needed to prove the bests stay apart")
        user_key = reflex_key(test_user_token)
        admin_key = reflex_key(admin_user_token)
        assert user_key != admin_key, "two accounts share one personal best"

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            page = context.new_page()
            page.goto(f"{base_url}/")
            page.evaluate(
                "([key, token]) => { localStorage.setItem(key, '1');"
                " localStorage.setItem('token', token); }",
                [user_key, test_user_token],
            )
            page.goto(f"{base_url}/")
            wait_for_nav(page)

            assert "Personal best stays at 1 ms" in self.run_once(page), (
                "the candidate's own best was not read back"
            )
            page.locator(".swal2-confirm").click()

            # Same profile, same machine, different account.
            page.evaluate(
                "(token) => localStorage.setItem('token', token)", admin_user_token
            )
            page.reload()
            wait_for_nav(page)

            assert "New personal best" in self.run_once(page), (
                "the admin inherited the candidate's personal best"
            )
            assert self.stored(page, user_key) == "1", (
                "the admin's run overwrote the candidate's best"
            )
            assert int(self.stored(page, admin_key) or 0) > 0, (
                "the admin's run was not stored under the admin's own key"
            )
        finally:
            context.close()


@pytest.mark.e2e
class TestNormalUserKeepsTheAccountUi:
    def test_home_offers_the_dashboard_and_the_account_menu(self, user_open):
        seen = observe(user_open("/"), "#home-primary-cta")
        assert USER_CTA in seen["ctaTexts"], (
            f"a candidate lost their dashboard link: {seen['ctaTexts']}"
        )
        assert any(h.endswith(DASHBOARD_PATH) for h in seen["ctaHrefs"]), (
            f"call-to-action never pointed at the dashboard: {seen['ctaHrefs']}"
        )
        assert seen["accountMenus"] == 1, "a candidate must keep the account dropdown"
        assert seen["adminHrefs"] == [], (
            f"a candidate must not be shown an admin route: {seen['adminHrefs']}"
        )

    def test_about_offers_the_dashboard(self, user_open):
        seen = observe(user_open(ABOUT_PATH), "#about-primary-cta")
        assert USER_CTA in seen["ctaTexts"], (
            f"a candidate lost their dashboard link on the about page: {seen['ctaTexts']}"
        )
        assert seen["accountMenus"] == 1

    def test_dashboard_is_not_taken_away_from_a_user(self, user_open):
        page = user_open(DASHBOARD_PATH)
        page.wait_for_selector("#app", state="attached", timeout=25000)
        page.wait_for_timeout(2500)
        assert DASHBOARD_PATH in page.url, (
            f"a normal user was redirected away from their own dashboard: {page.url}"
        )
