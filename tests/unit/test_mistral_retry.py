"""
Unit Tests — backend/services/mistral_retry.py
Tests: retry logic, circuit breaker open/close, rate-limit detection.
No real network calls.
"""
import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _reset_circuit():
    """Reset module-level circuit breaker state between tests."""
    import backend.services.mistral_retry as mr
    mr._cb_failure_count = 0
    mr._cb_open_until = 0.0


class TestIsRateLimit:
    def setup_method(self):
        _reset_circuit()

    def test_detects_429_string(self):
        from backend.services.mistral_retry import _is_rate_limit
        assert _is_rate_limit(Exception("Error 429 too many requests"))

    def test_detects_rate_limit_phrase(self):
        from backend.services.mistral_retry import _is_rate_limit
        assert _is_rate_limit(Exception("rate limit exceeded"))

    def test_detects_503_service_unavailable(self):
        from backend.services.mistral_retry import _is_rate_limit
        assert _is_rate_limit(Exception("503 service unavailable"))

    def test_does_not_flag_auth_error(self):
        from backend.services.mistral_retry import _is_rate_limit
        assert not _is_rate_limit(Exception("401 unauthorized"))

    def test_does_not_flag_bad_request(self):
        from backend.services.mistral_retry import _is_rate_limit
        assert not _is_rate_limit(Exception("400 bad request"))


class TestMistralCall:
    def setup_method(self):
        _reset_circuit()

    def test_success_on_first_attempt(self):
        from backend.services.mistral_retry import mistral_call
        fn = MagicMock(return_value="ok")
        assert mistral_call(fn) == "ok"
        fn.assert_called_once()

    def test_retries_on_rate_limit_then_succeeds(self):
        from backend.services.mistral_retry import mistral_call
        calls = [Exception("429 rate limit"), "success"]
        fn = MagicMock(side_effect=calls)
        with patch("backend.services.mistral_retry.time.sleep"):
            result = mistral_call(fn, max_retries=2)
        assert result == "success"
        assert fn.call_count == 2

    def test_raises_after_all_retries_exhausted(self):
        from backend.services.mistral_retry import mistral_call
        fn = MagicMock(side_effect=Exception("429 rate limit"))
        with patch("backend.services.mistral_retry.time.sleep"):
            with pytest.raises(Exception):
                mistral_call(fn, max_retries=2)
        assert fn.call_count == 3   # 1 original + 2 retries

    def test_non_retryable_error_raises_immediately(self):
        from backend.services.mistral_retry import mistral_call
        fn = MagicMock(side_effect=ValueError("invalid API key"))
        with pytest.raises(ValueError):
            mistral_call(fn, max_retries=2)
        fn.assert_called_once()   # no retries for non-rate-limit errors

    def test_resets_failure_count_on_success(self):
        import backend.services.mistral_retry as mr
        from backend.services.mistral_retry import mistral_call
        mr._cb_failure_count = 2   # simulate 2 previous failures
        fn = MagicMock(return_value="ok")
        mistral_call(fn)
        assert mr._cb_failure_count == 0

    def test_wait_called_between_retries(self):
        from backend.services.mistral_retry import mistral_call
        fn = MagicMock(side_effect=[Exception("429 rate limit"), "ok"])
        with patch("backend.services.mistral_retry.time.sleep") as mock_sleep:
            mistral_call(fn, max_retries=2, wait_seconds=2.0)
        mock_sleep.assert_called_once_with(2.0)


class TestCircuitBreaker:
    def setup_method(self):
        _reset_circuit()

    def test_circuit_opens_after_threshold(self):
        import backend.services.mistral_retry as mr
        from backend.services.mistral_retry import mistral_call
        fn = MagicMock(side_effect=Exception("429 rate limit"))
        with patch("backend.services.mistral_retry.time.sleep"):
            for _ in range(mr._CB_THRESHOLD):
                try:
                    mistral_call(fn, max_retries=0)
                except Exception:
                    pass
        # Circuit should now be open
        assert mr._cb_open_until > time.time()

    def test_open_circuit_raises_immediately_without_calling_fn(self):
        import backend.services.mistral_retry as mr
        from backend.services.mistral_retry import mistral_call
        mr._cb_open_until = time.time() + 30.0   # force open
        fn = MagicMock(return_value="ok")
        with pytest.raises(RuntimeError, match="AI_RATE_LIMIT"):
            mistral_call(fn)
        fn.assert_not_called()

    def test_closed_circuit_allows_calls(self):
        import backend.services.mistral_retry as mr
        from backend.services.mistral_retry import mistral_call
        mr._cb_open_until = 0.0   # ensure closed
        fn = MagicMock(return_value="result")
        assert mistral_call(fn) == "result"
