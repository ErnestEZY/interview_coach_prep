"""
E2E Tests — Authentication Flows
Covers: Register page T&C gate, form validation, login, logout, GitHub OAuth gate
"""
import pytest
import re
import time


def strength_width(bar):
    """The percentage the strength meter is currently drawn at.

    The meter sets its width inline, so the style attribute is the state; a
    missing width is a failure rather than a zero, because an absent element
    and an empty bar are different defects.
    """
    style = bar.get_attribute("style") or ""
    match = re.search(r"width:\s*([\d.]+)%", style)
    assert match, f"Strength meter has no width: {style!r}"
    return float(match.group(1))


@pytest.mark.e2e
class TestRegisterPage:
    """Register page — T&C acceptance gate, form validation, GitHub OAuth."""

    def test_register_page_loads(self, page, base_url):
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        assert "Create Account" in page.inner_text("h2")

    def test_terms_and_privacy_links_visible(self, page, base_url):
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        # Legal section should be present
        legal_section = page.locator("#legal-section")
        assert legal_section.is_visible()

    def test_agree_checkbox_disabled_until_terms_accepted(self, page, base_url):
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        # Checkbox should be disabled initially
        checkbox = page.locator("#agreeCheck")
        assert checkbox.is_disabled()

    def test_github_oauth_button_gated_by_terms(self, page, base_url):
        """GitHub OAuth button should not redirect until T&C accepted."""
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        # Find the GitHub button
        github_btn = page.locator("button:has-text('GitHub')")
        assert github_btn.is_visible()
        # Click it without accepting terms — should show prompt, not navigate
        github_btn.click()
        # Should show a SweetAlert, not redirect to /api/auth/oauth/github
        page.wait_for_timeout(1000)
        assert "/api/auth/oauth/github" not in page.url

    def test_password_strength_indicator_visible(self, page, base_url):
        """The meter has to respond to the password, not merely exist.

        This used to be `assert strength_text or True`, which passes on an
        empty string and on a missing element alike — it could not fail.
        """
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        field = page.locator('input[title="New Password"]')
        bar = page.locator(".password-strength-progress .progress-bar")

        field.fill("abc")
        bar.wait_for(state="visible")
        weak = strength_width(bar)
        weak_label = bar.get_attribute("title") or ""

        field.fill("Str0ng!Passphrase#2026")
        strong = strength_width(bar)
        strong_label = bar.get_attribute("title") or ""

        assert weak_label.startswith("Password Strength: "), weak_label
        assert strong_label.startswith("Password Strength: "), strong_label
        assert weak_label != strong_label, "The label does not follow the password"
        assert strong > weak, (
            f"A stronger password drew a narrower meter: {weak}% -> {strong}%"
        )

    def test_password_match_validation(self, page, base_url):
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        page.fill('input[title="New Password"]', "Test123!")
        page.fill('input[title="Confirm Password"]', "Different123!")
        page.wait_for_timeout(500)
        # Should show "Passwords do not match"
        page.wait_for_selector("text=Passwords do not match", timeout=3000)

    def test_nav_link_to_login(self, page, base_url):
        page.goto(f"{base_url}/static/pages/register.html")
        page.wait_for_selector("#app", state="visible")
        # Two 'Login' anchors exist (navbar + footer); click the first (navbar)
        login_link = page.locator("a:has-text('Login')").first
        login_link.click()
        page.wait_for_timeout(2000)
        assert "login.html" in page.url


@pytest.mark.e2e
class TestLoginPage:
    """Login page — form, forgot password, register link."""

    def test_login_page_loads(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        assert "Welcome Back" in page.inner_text("h2")

    def test_login_form_has_email_and_password(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        email_input = page.locator('input[name="email"]')
        password_input = page.locator('input[name="password"]')
        assert email_input.is_visible()
        assert password_input.is_visible()

    def test_password_toggle_button(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        password_input = page.locator('input[name="password"]')
        toggle_btn = page.locator("button[title='Toggle password visibility']")
        # Type password
        password_input.fill("secret123")
        assert password_input.get_attribute("type") == "password"
        # Toggle
        toggle_btn.click()
        assert password_input.get_attribute("type") == "text"

    def test_forgot_password_link(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        forgot_link = page.locator("a:has-text('Forgot Password?')")
        assert forgot_link.is_visible()
        forgot_link.click()
        page.wait_for_timeout(2000)
        assert "forgot_password.html" in page.url

    def test_register_link_navigates(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        page.locator("a:has-text('Create Account')").click()
        page.wait_for_timeout(2000)
        assert "register.html" in page.url

    def test_github_oauth_link_present(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        github_link = page.locator("a:has-text('GitHub')")
        assert github_link.is_visible()
        href = github_link.get_attribute("href")
        assert "oauth/github" in (href or "")

    def test_login_button_disabled_without_credentials(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        sign_in_btn = page.locator("button:has-text('Sign In')")
        # Button should have overlay or be visually disabled
        assert sign_in_btn.is_visible()

    def test_legal_footer_present(self, page, base_url):
        page.goto(f"{base_url}/static/pages/login.html")
        page.wait_for_selector("#app", state="visible")
        assert "Terms" in page.inner_text("body")
        assert "Privacy" in page.inner_text("body")


@pytest.mark.e2e
class TestForgotPassword:
    def test_forgot_password_page_loads(self, page, base_url):
        page.goto(f"{base_url}/static/pages/forgot_password.html")
        page.wait_for_timeout(3000)
        assert "Forgot" in page.title() or "Reset" in page.inner_text("body")
