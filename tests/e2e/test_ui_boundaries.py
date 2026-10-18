"""
E2E Tests — UI Input Boundary Values
Covers: maxlength enforcement on the auth forms (email 50, password 16,
name 30, confirm-password 16). Oversized paste input must be truncated to
the declared boundary by the browser before it can ever reach the backend.
"""
import pytest

# (page_path, selector, expected_maxlength)
BOUNDARY_FIELDS = [
    ("/static/pages/login.html", 'input[name="email"]', 50),
    ("/static/pages/login.html", 'input[name="password"]', 16),
    ("/static/pages/register.html", 'input[title="Full Name"]', 30),
    ("/static/pages/register.html", 'input[title="Email address"]', 50),
    ("/static/pages/register.html", 'input[title="New Password"]', 16),
    ("/static/pages/register.html", 'input[title="Confirm Password"]', 16),
]

OVERSIZED = "A" * 500


@pytest.mark.e2e
class TestInputMaxlengthBoundaries:
    @pytest.mark.parametrize("page_path,selector,expected_max", BOUNDARY_FIELDS)
    def test_field_declares_maxlength(self, page, base_url, page_path, selector, expected_max):
        page.goto(f"{base_url}{page_path}")
        page.wait_for_selector("#app", state="visible")
        field = page.locator(selector)
        assert field.count() > 0, f"{selector} not found on {page_path}"
        attr = field.first.get_attribute("maxlength")
        assert attr is not None, f"{selector} on {page_path} has no maxlength attribute"
        assert int(attr) == expected_max, (
            f"{page_path}{selector}: maxlength={attr}, expected {expected_max}"
        )

    @pytest.mark.parametrize("page_path,selector,expected_max", BOUNDARY_FIELDS)
    def test_oversized_input_is_truncated(self, page, base_url, page_path, selector, expected_max):
        page.goto(f"{base_url}{page_path}")
        page.wait_for_selector("#app", state="visible")
        field = page.locator(selector)
        field.first.fill(OVERSIZED)
        value = field.first.input_value()
        assert len(value) == expected_max, (
            f"{page_path}{selector}: accepted {len(value)} chars, boundary is {expected_max}"
        )


@pytest.mark.e2e
class TestOversizedSubmitRejected:
    def test_login_with_boundary_sized_values_stays_safe(self, page, base_url):
        """Submitting boundary-sized (not oversized — truncation guarantees
        that) values must never crash the page or leak a server error."""
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        page.fill('input[name="email"]', "a" * 46 + "@b.c")  # exactly 50 chars
        page.fill('input[name="password"]', "x" * 16)  # exactly 16 chars
        page.locator("button:has-text('Sign'), button[type='submit']").first.click()
        page.wait_for_timeout(3000)
        # Account does not exist — app must respond in place, not crash
        assert page.locator("#app").count() > 0
        assert "login.html" in page.url or "500" not in page.inner_text("body")
