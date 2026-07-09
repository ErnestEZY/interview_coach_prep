"""
Mistral API retry utility.

Wraps any callable that hits the Mistral API with a simple fixed-wait retry
on rate-limit (429) and transient server errors (5xx).

Design decisions for FYP:
- Max 2 retries  → total 3 attempts, predictable timing (~4s worst case)
- Fixed 2s wait  → easy to explain, no exponential complexity
- Only retries on 429 / 500 / 503 — not on auth errors or bad requests
- Circuit breaker: after 3 consecutive 429s within 60s, fast-fail for 30s
  so a stuck user doesn't hammer the API during a live demo
- Never alters the return value or side effects of the wrapped call
"""

import time
import logging
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ── Circuit breaker state (module-level, shared across workers in same process) ──
_cb_failure_count: int = 0
_cb_open_until: float = 0.0      # epoch seconds; 0 = closed
_CB_THRESHOLD: int = 3           # consecutive 429s to open circuit
_CB_OPEN_SECONDS: float = 30.0   # how long to stay open


def _is_rate_limit(exc: Exception) -> bool:
    """Return True if the exception looks like a Mistral 429 or 5xx."""
    msg = str(exc).lower()
    return any(k in msg for k in ("429", "rate limit", "too many requests",
                                  "500", "503", "service unavailable",
                                  "upstream", "overloaded"))


def mistral_call(fn: Callable[[], T], max_retries: int = 2, wait_seconds: float = 2.0) -> T:
    """
    Call `fn()` (a zero-argument lambda wrapping a Mistral API call).
    Retries up to `max_retries` times on rate-limit / server errors.
    Raises the last exception if all attempts fail.

    Usage:
        result = mistral_call(lambda: client.chat.complete(...))
    """
    global _cb_failure_count, _cb_open_until

    # ── Circuit breaker check ────────────────────────────────────────────────
    now = time.time()
    if _cb_open_until > now:
        remaining = int(_cb_open_until - now)
        raise RuntimeError(
            f"AI_RATE_LIMIT: System is resting after repeated rate limits. "
            f"Retrying automatically in ~{remaining}s."
        )

    last_exc: Exception = RuntimeError("No attempt made")
    for attempt in range(max_retries + 1):
        try:
            result = fn()
            # Success — reset circuit breaker
            _cb_failure_count = 0
            return result
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit(exc):
                _cb_failure_count += 1
                logger.warning(
                    "Mistral rate-limit hit (attempt %d/%d, cb_count=%d): %s",
                    attempt + 1, max_retries + 1, _cb_failure_count, exc
                )
                # Open circuit if threshold reached
                if _cb_failure_count >= _CB_THRESHOLD:
                    _cb_open_until = time.time() + _CB_OPEN_SECONDS
                    logger.warning(
                        "Circuit breaker OPEN — cooling down for %.0fs", _CB_OPEN_SECONDS
                    )
                    raise RuntimeError(
                        f"AI_RATE_LIMIT: High demand detected. "
                        f"Please wait ~{int(_CB_OPEN_SECONDS)}s and try again."
                    ) from exc
                if attempt < max_retries:
                    logger.info("Waiting %.1fs before retry %d…", wait_seconds, attempt + 2)
                    time.sleep(wait_seconds)
            else:
                # Non-retryable error — raise immediately
                raise

    raise last_exc
