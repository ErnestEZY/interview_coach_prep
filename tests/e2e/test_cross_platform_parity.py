"""Cross-platform parity assertions.

The suite is engine-agnostic: CI runs it under Chromium, Firefox and WebKit
(nightly / manual matrix). These tests pin the contracts that must behave the
same everywhere — viewport meta, core copy, API JSON contract, JS baseline,
password toggle, native email validation and offline signalling.
"""
import pytest

pytestmark = pytest.mark.e2e

HOME = "/"
LOGIN = "/static/pages/login.html"
ABOUT = "/static/pages/about.html"


class TestShellParity:
    def test_mobile_viewport_meta_present(self, page, base_url):
        page.goto(f"{base_url}{HOME}")
        content = page.get_attribute('meta[name="viewport"]', "content")
        assert content, "No viewport meta tag"
        assert "width=device-width" in content

    def test_core_copy_renders_on_home_and_login(self, page, base_url):
        page.goto(f"{base_url}{HOME}")
        page.wait_for_selector("text=Master Your Next Interview")
        page.goto(f"{base_url}{LOGIN}")
        page.wait_for_selector("text=Welcome Back")
        assert page.locator("text=Email Address").count() >= 1
        assert page.locator("text=Password").count() >= 1

    def test_offline_overlay_is_present_in_dom(self, page, base_url):
        page.goto(f"{base_url}{HOME}")
        page.wait_for_selector("text=Master Your Next Interview")
        assert page.locator("#offline-overlay").count() == 1

    def test_about_page_renders(self, page, base_url):
        page.goto(f"{base_url}{ABOUT}")
        page.wait_for_selector("text=Career Launchpad")
        assert page.title()


class TestApiContractParity:
    def test_config_contract_is_stable(self, page, base_url):
        response = page.request.get(f"{base_url}/api/auth/config")
        assert response.status == 200
        assert "application/json" in response.headers.get("content-type", "")
        payload = response.json()
        for key in (
            "emailjs_public_key",
            "emailjs_service_id",
            "emailjs_template_id",
            "careerjet_widget_id",
        ):
            assert key in payload, f"Missing contract key: {key}"

    def test_unauthorized_contract_is_stable(self, page, base_url):
        response = page.request.get(f"{base_url}/api/auth/me")
        assert response.status == 401
        assert "detail" in response.json()

    def test_unknown_route_contract(self, page, base_url):
        response = page.request.get(f"{base_url}/api/not-a-real-route")
        assert response.status == 404
        assert "detail" in response.json()


class TestRuntimeBaseline:
    def test_js_baseline_capabilities_exist(self, page, base_url):
        page.goto(f"{base_url}{HOME}")
        caps = page.evaluate(
            """() => ({
                fetch: typeof fetch,
                promise: typeof Promise,
                storage: typeof localStorage,
                serviceWorker: 'serviceWorker' in navigator,
                visibility: typeof document.visibilityState,
            })"""
        )
        assert caps["fetch"] == "function"
        assert caps["promise"] == "function"
        assert caps["storage"] == "object"
        assert caps["serviceWorker"] is True
        assert caps["visibility"] == "string"

    def test_password_toggle_switches_input_type(self, page, base_url):
        page.goto(f"{base_url}{LOGIN}")
        page.wait_for_selector("text=Welcome Back")
        password = page.locator('input[name="password"]')
        assert password.get_attribute("type") == "password"
        toggle = page.locator("button.password-toggle-btn")
        toggle.click()
        assert password.get_attribute("type") == "text"
        toggle.click()
        assert password.get_attribute("type") == "password"

    def test_native_email_validation_blocks_bad_input(self, page, base_url):
        page.goto(f"{base_url}{LOGIN}")
        page.wait_for_selector("text=Welcome Back")
        page.fill('input[name="email"]', "not-an-email")
        page.fill('input[name="password"]', "SomePass1!")
        valid = page.evaluate(
            "document.querySelector('input[name=email]').validity.valid"
        )
        assert valid is False, "Engine accepted an invalid email address"


class TestOfflineParity:
    def test_api_transport_loss_surfaces_as_network_error(self, browser, base_url):
        """A hard transport failure (DNS/TCP loss) must surface as a rejected
        request on every engine, not as a silent success.

        Service workers are blocked here: Firefox does not route SW-issued
        fetches through Playwright, so a controlled SW would hide the loss.
        """
        context = browser.new_context(service_workers="block")
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{base_url}{HOME}")
            page.wait_for_selector("text=Master Your Next Interview")

            context.route("**/api/**", lambda route: route.abort())
            result = page.evaluate(
                """() => fetch('/api/auth/config')
                    .then(r => 'http-' + r.status)
                    .catch(() => 'network-error')"""
            )
            assert result == "network-error", result
            assert errors == [], f"Uncaught errors on transport loss: {errors}"
        finally:
            context.close()

    def test_device_offline_signal_shows_overlay(self, page, base_url):
        page.goto(f"{base_url}{HOME}")
        page.wait_for_selector("text=Master Your Next Interview")

        page.context.set_offline(True)
        try:
            page.wait_for_function(
                "document.querySelector('#offline-overlay.active') !== null",
                timeout=15000,
            )
        finally:
            page.context.set_offline(False)
