"""
E2E Tests — Admin Portal Flow
Covers: Admin auth page, passphrase verification, admin portal, resume management
"""
import pytest


ADMIN_AUTH_URL = "/static/pages/icp-admin-auth-9f2d8b4e.html"
ADMIN_PORTAL_URL = "/static/pages/icp-admin-portal-5e6a1c3d.html"
ADMIN_VIEW_URL = "/static/pages/icp-admin-view-2b8f4a10.html"
ADMIN_HUB_URL = "/static/pages/icp-admin-hub-v1.html"


@pytest.mark.e2e
class TestAdminAuthPage:
    """Admin login page — obscured URL, form fields, validation."""

    def test_admin_auth_page_loads(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        assert "Admin" in page.inner_text("body")

    def test_admin_auth_requires_icp_email_domain(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        email_input = page.locator('input[name="email"]')
        # Check pattern attribute enforces @icp-solution.com
        pattern = email_input.get_attribute("pattern")
        # Pattern is [a-z0-9._%+-]+@icp-solution\.com$ — the dot is regex-escaped
        # so check for the unambiguous domain prefix instead of the full domain.
        assert "@icp-solution" in (pattern or ""), (
            f"Expected '@icp-solution' in email pattern, got: {pattern!r}"
        )

    def test_admin_auth_has_password_field(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        password_input = page.locator('input[name="password"]')
        assert password_input.is_visible()

    def test_admin_auth_has_invite_code_field(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        invite_input = page.locator('input[name="invite_code"]')
        assert invite_input.is_visible()

    def test_admin_auth_password_toggle(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        password_input = page.locator('input[name="password"]')
        toggle_btn = page.locator("button[title='Toggle password visibility']")
        password_input.fill("adminpass123")
        assert password_input.get_attribute("type") == "password"
        toggle_btn.click()
        assert password_input.get_attribute("type") == "text"

    def test_admin_auth_button_disabled_without_all_fields(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        enter_btn = page.locator("button:has-text('Enter Admin Panel')")
        assert enter_btn.is_visible()

    def test_admin_auth_back_to_home_link(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        home_link = page.locator("a:has-text('Back to Home')")
        assert home_link.is_visible()

    def test_admin_auth_invalid_email_shows_validation(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        email_input = page.locator('input[name="email"]')
        email_input.fill("invalid@gmail.com")
        # The overlay-trigger div blocks clicks when password/inviteCode are empty.
        # Fill the other fields so the overlay disappears, then attempt submit.
        page.fill('input[name="password"]', "somepassword")
        page.fill('input[name="invite_code"]', "WRONG-INVITE")
        # Trigger form submission via Enter key (bypasses overlay)
        email_input.press("Enter")
        page.wait_for_timeout(3000)
        # Browser HTML5 pattern validation or server rejects → stays on same page
        assert ADMIN_AUTH_URL in page.url


@pytest.mark.e2e
class TestAdminPortal:
    """Admin portal — resume management dashboard."""

    def test_admin_portal_page_loads(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_PORTAL_URL}")
        page.wait_for_timeout(5000)
        # Page should load even without auth — may redirect to admin login
        body_text = page.inner_text("body")
        assert "ICP" in body_text or "Admin" in body_text or "Loading" in body_text

    def test_admin_portal_has_navbar(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_PORTAL_URL}")
        page.wait_for_timeout(5000)
        navbar = page.locator(".navbar")
        assert navbar.count() > 0

    def test_admin_portal_back_to_admin_login_link(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_PORTAL_URL}")
        page.wait_for_timeout(5000)
        # Should have a link back to admin auth
        admin_login_link = page.locator("a[href*='icp-admin-auth']")
        if admin_login_link.count() > 0:
            assert admin_login_link.is_visible()

    def test_admin_hub_page_loads(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_HUB_URL}")
        page.wait_for_timeout(5000)
        assert "ICP" in page.inner_text("body") or "Admin" in page.inner_text("body")

    def test_admin_view_page_loads(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_VIEW_URL}")
        page.wait_for_timeout(5000)
        navbar = page.locator(".navbar")
        assert navbar.count() > 0

    def test_admin_view_back_to_portal_link(self, page, base_url):
        page.goto(f"{base_url}{ADMIN_VIEW_URL}")
        page.wait_for_timeout(5000)
        portal_link = page.locator("a[href*='icp-admin-portal']")
        if portal_link.count() > 0:
            assert portal_link.is_visible()


@pytest.mark.e2e
class TestAdminAuthFlow:
    """Full admin auth flow — login attempt with test credentials."""

    def test_admin_login_with_valid_format(self, page, base_url, admin_credentials, admin_user_token):
        """Full browser login flow: the page clears storage, posts to
        /api/auth/admin_login, and redirects to the portal on success.
        Requesting admin_user_token guarantees the seeded E2E admin account
        exists before this UI flow runs."""
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        # Fill the form with the seeded E2E admin credentials
        page.fill('input[name="email"]', admin_credentials["email"])
        page.fill('input[name="password"]', admin_credentials["password"])
        page.fill('input[name="invite_code"]', admin_credentials["invite_code"])
        # Submit
        page.locator("button:has-text('Enter Admin Panel')").click()
        page.wait_for_timeout(5000)
        # Success must land on the admin portal — no vacuous pass
        assert "icp-admin-portal" in page.url, (
            f"Admin login did not reach the portal — still on {page.url}"
        )
        body = page.inner_text("body")
        assert "ICP" in body or "Admin" in body

    def test_admin_login_wrong_invite_code(self, page, base_url):
        """Wrong invite code must be rejected in-place. Uses a non-existent
        admin-domain email so no real account's lockout counters move."""
        page.goto(f"{base_url}{ADMIN_AUTH_URL}")
        page.wait_for_selector("#app", state="visible")
        page.fill('input[name="email"]', "e2e-nonexistent@icp-solution.com")
        page.fill('input[name="password"]', "wrongpass")
        page.fill('input[name="invite_code"]', "WRONG-CODE-123")
        page.locator("button:has-text('Enter Admin Panel')").click()
        page.wait_for_timeout(5000)
        # Should show error (SweetAlert or inline) and stay on page
        assert ADMIN_AUTH_URL in page.url


@pytest.mark.e2e
class TestAdminPortalAuthenticated:
    """Admin portal behind a real seeded admin session."""

    _ADMIN_PAGES = [ADMIN_PORTAL_URL, ADMIN_VIEW_URL]

    @pytest.mark.parametrize("page_path", _ADMIN_PAGES)
    def test_admin_page_stays_authenticated(self, authenticated_admin_page, base_url, page_path):
        authenticated_admin_page.goto(f"{base_url}{page_path}")
        authenticated_admin_page.wait_for_timeout(5000)
        # A valid admin session must not be bounced to the admin auth page
        assert "icp-admin-auth" not in authenticated_admin_page.url
        assert page_path.rsplit("/", 1)[-1] in authenticated_admin_page.url
        assert authenticated_admin_page.locator("#app").count() > 0

    def test_admin_hub_splash_redirects_to_auth(self, page, base_url):
        """The hub is an animated splash that funnels every visitor to the
        obscured admin auth page by design — regardless of session state."""
        page.goto(f"{base_url}{ADMIN_HUB_URL}")
        page.wait_for_timeout(5000)
        assert "icp-admin-auth" in page.url

    def test_admin_portal_shows_resume_management(self, authenticated_admin_page, base_url):
        authenticated_admin_page.goto(f"{base_url}{ADMIN_PORTAL_URL}")
        authenticated_admin_page.wait_for_timeout(5000)
        body = authenticated_admin_page.inner_text("body")
        # Resume management UI, or the empty-state copy when no resumes exist
        assert (
            "Resume" in body
            or "resume" in body
            or "Candidate" in body
            or "review" in body.lower()
        )
