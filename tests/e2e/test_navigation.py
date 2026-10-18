"""
E2E Tests — Navigation & Page Availability
Covers: All static pages load correctly, nav links, responsive layout
"""
import pytest


PAGES = [
    "/static/pages/login.html",
    "/static/pages/register.html",
    "/static/pages/verify.html",
    "/static/pages/forgot_password.html",
    "/static/pages/reset_password.html",
    "/static/pages/dashboard.html",
    "/static/pages/interview.html",
    "/static/pages/history.html",
    "/static/pages/resume_builder.html",
    "/static/pages/find-jobs.html",
    "/static/pages/about.html",
    "/static/pages/privacy.html",
]

# Auth-protected pages redirect anonymous visitors to login.html before
# Vue mounts — they are mount-checked against an authenticated session below.
AUTH_PROTECTED_PAGES = [
    "/static/pages/dashboard.html",
    "/static/pages/history.html",
    "/static/pages/resume_builder.html",
    "/static/pages/find-jobs.html",
]


@pytest.mark.e2e
class TestPageAvailability:
    """Every page should return 200 and have the Vue mount point."""

    @pytest.mark.parametrize("page_path", PAGES)
    def test_page_returns_200(self, page, base_url, page_path):
        response = page.goto(f"{base_url}{page_path}")
        if response is None:
            # A client-side redirect raced the response capture — retry once
            # to obtain a definite response rather than skipping.
            response = page.goto(f"{base_url}{page_path}")
        assert response is not None, f"No response captured for {page_path}"
        assert response.status == 200, f"{page_path} returned {response.status}"

    # Auth-protected pages are mount-checked against an authenticated session.
    @pytest.mark.parametrize(
        "page_path",
        [p for p in PAGES if p != "/static/pages/privacy.html" and p not in AUTH_PROTECTED_PAGES],
    )
    def test_page_has_vue_mount(self, page, base_url, page_path):
        page.goto(f"{base_url}{page_path}")
        page.wait_for_timeout(3000)
        app = page.locator("#app")
        assert app.count() > 0, f"#app not found on {page_path}"

    @pytest.mark.parametrize("page_path", AUTH_PROTECTED_PAGES)
    def test_auth_protected_page_has_vue_mount(self, authenticated_page, base_url, page_path):
        """These pages redirect anonymous visitors, so the mount check
        runs against an authenticated session and must not bounce."""
        authenticated_page.goto(f"{base_url}{page_path}")
        authenticated_page.wait_for_timeout(3000)
        assert page_path in authenticated_page.url, (
            f"Expected to stay on {page_path}, got {authenticated_page.url}"
        )
        app = authenticated_page.locator("#app")
        assert app.count() > 0, f"#app not found on {page_path} (authenticated)"

    @pytest.mark.parametrize("page_path", PAGES)
    def test_page_has_favicon(self, page, base_url, page_path):
        page.goto(f"{base_url}{page_path}")
        favicon = page.locator('link[rel="icon"]')
        assert favicon.count() > 0, f"No favicon on {page_path}"


@pytest.mark.e2e
class TestHomePage:
    def test_home_page_loads(self, page, base_url):
        page.goto(base_url)
        page.wait_for_timeout(3000)
        assert "Interview Coach Prep" in page.inner_text("body") or "ICP" in page.inner_text("body")

    def test_home_page_has_feature_steps(self, page, base_url):
        page.goto(base_url)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        assert "Resume" in body or "Interview" in body

    def test_home_page_links_to_login(self, page, base_url):
        page.goto(base_url)
        page.wait_for_timeout(3000)
        # Look for login/register links
        links = page.locator("a[href*='login'], a[href*='register']")
        assert links.count() > 0


@pytest.mark.e2e
class TestResponsiveLayout:
    """Test that pages are responsive on mobile viewport."""

    @pytest.mark.parametrize("page_path", [
        "/static/pages/login.html",
        "/static/pages/register.html",
        "/static/pages/dashboard.html",
    ])
    def test_mobile_viewport_no_horizontal_scroll(self, page, base_url, page_path):
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(f"{base_url}{page_path}")
        page.wait_for_timeout(3000)
        # Check no horizontal scroll
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 5, f"Horizontal scroll on {page_path} (mobile)"

    @pytest.mark.parametrize("page_path", [
        "/static/pages/login.html",
        "/static/pages/register.html",
    ])
    def test_desktop_viewport_renders(self, page, base_url, page_path):
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{base_url}{page_path}")
        page.wait_for_timeout(3000)
        app = page.locator("#app")
        assert app.is_visible()
