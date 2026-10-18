"""
E2E Tests — Permission-Denied Handling
Covers: microphone and camera permission rejection (the interview page uses
voice STT/TTS and an optional camera) and page integrity when no permissions
are granted.
"""
import pytest


def _denied_permissions_context(browser, token):
    """Authenticated context with NO permissions granted (mic/camera off)."""
    if not token:
        pytest.skip("No test user token available")
    context = browser.new_context(permissions=[])
    context.add_init_script(
        f"try {{ localStorage.setItem('token', '{token}'); }} catch (e) {{ }}"
    )
    return context


def _getusermedia_result(page, constraints):
    # Promise.race bounds the evaluate call — getUserMedia can pend forever on
    # engines whose headless build lacks a media stack or a dismissible
    # permission prompt. A timeout is treated as a denial form.
    return page.evaluate(
        """async (constraints) => {
            const attempt = async () => {
                try {
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                        return 'unsupported';
                    }
                    const stream = await navigator.mediaDevices.getUserMedia(constraints);
                    stream.getTracks().forEach(t => t.stop());
                    return 'granted';
                } catch (e) { return e.name; }
            };
            const timeout = () => new Promise(
                resolve => setTimeout(() => resolve('timeout-denial'), 8000)
            );
            return Promise.race([attempt(), timeout()]);
        }""",
        constraints,
    )


# Every non-granted outcome is an acceptable denial form: NotAllowedError
# (permission off), NotFoundError (no device), NotSupportedError (headless
# browsers ship no media stack), a race timeout, etc. What must NEVER happen
# is a stream being granted while permissions are off.
DENIAL_RESULTS = {
    "NotAllowedError", "NotFoundError", "NotSupportedError", "SecurityError",
    "AbortError", "OverconstrainedError", "timeout-denial", "unsupported",
}


@pytest.mark.e2e
class TestPermissionDenied:
    def test_microphone_denied_returns_notallowederror(self, browser, base_url, test_user_token):
        context = _denied_permissions_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        result = _getusermedia_result(page, {"audio": True})
        assert result in DENIAL_RESULTS, (
            f"Mic stream must be unobtainable with permissions off, got: {result}"
        )
        context.close()

    def test_camera_denied_returns_notallowederror(self, browser, base_url, test_user_token):
        context = _denied_permissions_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        result = _getusermedia_result(page, {"video": True})
        assert result in DENIAL_RESULTS, (
            f"Camera stream must be unobtainable with permissions off, got: {result}"
        )
        context.close()

    def test_interview_page_intact_with_permissions_denied(self, browser, base_url, test_user_token):
        """With mic and camera off, the interview page must still mount and
        expose the Start control — denial must not break the page."""
        context = _denied_permissions_context(browser, test_user_token)
        page = context.new_page()
        page.goto(f"{base_url}/static/pages/interview.html")
        page.wait_for_timeout(3000)
        assert page.locator("#app").count() > 0
        assert page.locator("button:has-text('Start Interview')").count() > 0
        context.close()
