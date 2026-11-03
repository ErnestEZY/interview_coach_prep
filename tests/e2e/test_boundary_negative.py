"""Boundary values and negative flows on the auth surfaces.

Complements test_ui_boundaries.py (attribute checks) with behavioural
assertions: typed-input truncation, OTP sanitisation, reset-link failure
modes, redirect guards, and backend rejection contracts. No shared E2E
account is mutated (unknown emails only), so the suite is safe to run
alongside the rest of the E2E set.
"""
import uuid

import pytest

pytestmark = pytest.mark.e2e

LOGIN = "/static/pages/login.html"


def _open_login(page, base_url):
    page.goto(f"{base_url}{LOGIN}")
    page.wait_for_selector("text=Welcome Back")


def _swal(page):
    popup = page.locator(".swal2-popup")
    popup.wait_for(state="visible", timeout=20000)
    return popup


class TestTypedBoundaries:
    def test_password_input_caps_at_16(self, page, base_url):
        _open_login(page, base_url)
        field = page.locator('input[name="password"]')
        field.fill("A" * 17)
        assert field.input_value() == "A" * 16

    def test_email_input_caps_at_50(self, page, base_url):
        _open_login(page, base_url)
        field = page.locator('input[name="email"]')
        field.fill("a" * 45 + "@b.co")  # exactly 50
        assert len(field.input_value()) == 50
        field.fill("a" * 46 + "@b.co")  # 51 -> must truncate
        assert len(field.input_value()) == 50

    def test_otp_accepts_digits_only_and_caps_at_six(self, page, base_url):
        page.goto(f"{base_url}/static/pages/verify.html?email=nobody%40example.com")
        page.wait_for_selector("#app", state="visible")
        otp = page.locator('input[name="otp"]')
        otp.fill("12a34b5c67")
        value = otp.input_value()
        assert value.isdigit(), f"OTP kept non-digits: {value!r}"
        assert len(value) <= 6, f"OTP exceeded six digits: {value!r}"


class TestNegativeFlows:
    def test_empty_login_prompts_incomplete_fields(self, page, base_url):
        _open_login(page, base_url)
        page.locator(".btn-overlay-trigger").click()
        assert "Incomplete Fields" in _swal(page).inner_text()

    def test_unknown_account_shows_login_failed(self, page, base_url):
        _open_login(page, base_url)
        page.fill('input[name="email"]', f"nobody-{uuid.uuid4().hex[:8]}@example.com")
        page.fill('input[name="password"]', "WrongPass123!")
        page.locator('button[type="submit"]').click()
        popup = page.locator(".swal2-popup:has-text('Login Failed')")
        popup.wait_for(state="visible", timeout=20000)
        # Dialog must carry a reason, not just the generic title
        assert popup.inner_text().strip().lower() != "login failed"

    def test_wrong_otp_shows_failure_dialog(self, page, base_url):
        page.goto(
            f"{base_url}/static/pages/verify.html"
            f"?email=nobody-{uuid.uuid4().hex[:8]}%40example.com"
        )
        page.wait_for_selector("#app", state="visible")
        page.fill('input[name="otp"]', "123456")
        page.locator('button:has-text("Verify Account")').click()
        # The dialog opens as a loading state ("Verifying...") and is then
        # replaced by the outcome, so wait for that transition first.
        page.wait_for_function(
            "() => { const p = document.querySelector('.swal2-popup');"
            " return !!p && !/verifying/i.test(p.innerText); }",
            timeout=20000,
        )
        text = page.locator(".swal2-popup").inner_text().lower()
        assert "invalid code" in text or "too many attempts" in text, text
        assert any(
            word in text for word in ("invalid", "fail", "expired", "too many", "not found", "error")
        ), text

    def test_reset_link_without_token_is_rejected(self, page, base_url):
        page.goto(f"{base_url}/static/pages/reset_password.html")
        page.locator(".swal2-popup:has-text('Invalid Link')").wait_for(
            state="visible", timeout=10000
        )

    def test_reset_link_with_garbage_token_is_rejected(self, page, base_url):
        page.goto(f"{base_url}/static/pages/reset_password.html?token=not-a-real-token")
        popup = page.locator(".swal2-popup:has-text('Invalid Link')")
        popup.wait_for(state="visible", timeout=20000)
        assert "expired or invalid" in popup.inner_text().lower()

    def test_protected_pages_redirect_when_unauthenticated(self, page, base_url):
        for path in (
            "/static/pages/dashboard.html",
            "/static/pages/find-jobs.html",
            "/static/pages/history.html",
            "/static/pages/resume_builder.html",
        ):
            page.goto(f"{base_url}{path}")
            page.wait_for_url("**/login.html", timeout=20000)

    def test_interview_start_is_disabled_without_resume(self, page, base_url):
        """Anonymous users have no resume, so the start control must stay
        disabled and the page must explain why (no silent dead end)."""
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_selector("#app", state="visible")
        start = page.locator("button:has-text('Start Interview')").first
        if start.count() == 0:
            pytest.skip("Interview start control not rendered in this engine")
        assert start.is_disabled(), "Start Interview must be disabled without a resume"
        body = page.locator("#app").inner_text().lower()
        assert "resume required" in body or "upload your resume" in body, body[:400]


class TestBackendRejectionContracts:
    def test_me_requires_bearer_token(self, page, base_url):
        r = page.request.get(f"{base_url}/api/auth/me")
        assert r.status == 401
        assert "detail" in r.json()

    def test_register_rejects_invalid_email(self, page, base_url):
        r = page.request.post(
            f"{base_url}/api/auth/register",
            data={"email": "not-an-email", "password": "StrongPass1!"},
        )
        assert r.status == 422

    def test_register_rejects_xss_email(self, page, base_url):
        r = page.request.post(
            f"{base_url}/api/auth/register",
            data={"email": "<script>alert(1)</script>@x.com", "password": "StrongPass1!"},
        )
        assert r.status == 422

    def test_login_rejects_missing_credentials(self, page, base_url):
        r = page.request.post(f"{base_url}/api/auth/login", data={})
        assert r.status in (400, 422)
