"""Unit tests for Rate Limiters.

Consolidated tests for SlidingWindowRateLimiter and its subclasses to avoid code duplication.
"""

from __future__ import annotations

import threading
from time import monotonic

import pytest

from src.api.chat_rate_limiter import ChatRateLimiter
from src.api.rate_limiter import LoginRateLimiter
from src.api.rate_limiter_base import SlidingWindowRateLimiter
from src.api.share_rate_limiter import ShareRateLimiter


@pytest.fixture(
    params=[
        (LoginRateLimiter, {"max_attempts": 3, "window_seconds": 10}),
        (ChatRateLimiter, {"max_requests": 3, "window_seconds": 10}),
        (ShareRateLimiter, {"max_requests": 3, "window_seconds": 10}),
        # Test base class directly too
        (SlidingWindowRateLimiter, {"max_requests": 3, "window_seconds": 10}),
    ]
)
def limiter(request):
    """Fixture to provide different rate limiter instances."""
    cls, kwargs = request.param
    return cls(**kwargs)


class TestRateLimiter:
    """Consolidated tests for all rate limiters."""

    def _check_limit_no_side_effect(self, limiter, ip: str) -> bool:
        """Helper to check limit status WITHOUT consuming a token (if possible).

        For LoginRateLimiter, is_blocked is side-effect free (read-only regarding count).
        For Chat/Share, is_limited consumes a token.
        So for consistent assertions, we should peek at internal state for Chat/Share/Base.
        """
        if isinstance(limiter, LoginRateLimiter):
            return limiter.is_blocked(ip)
        else:
            # Base class / Chat / Share inspection
            with limiter._lock:
                limiter._prune(ip)
                return limiter._is_limit_reached(ip)

    def _record_action(self, limiter, ip: str):
        """Helper to record an action/failure."""
        if isinstance(limiter, LoginRateLimiter):
            limiter.record_failure(ip)
        elif hasattr(limiter, "is_limited"):
            # is_limited adds timestamp if not limited
            # If limited, it doesn't add. But we want to "try" to record.
            limiter.is_limited(ip)
        else:
            with limiter._lock:
                limiter._add_timestamp(ip)

    def test_not_limited_initially(self, limiter):
        """A new IP is not limited."""
        assert self._check_limit_no_side_effect(limiter, "192.168.1.1") is False

    def test_limiting_logic(self, limiter):
        """Test the core limiting logic (under limit, at limit, over limit)."""
        # Max is 3
        # 1st
        self._record_action(limiter, "192.168.1.1")
        assert self._check_limit_no_side_effect(limiter, "192.168.1.1") is False  # (1/3)

        # 2nd
        self._record_action(limiter, "192.168.1.1")
        assert self._check_limit_no_side_effect(limiter, "192.168.1.1") is False  # (2/3)

        # 3rd (Limit reached)
        self._record_action(limiter, "192.168.1.1")

        # Next check should be blocked
        assert self._check_limit_no_side_effect(limiter, "192.168.1.1") is True

        # 4th (Over limit)
        self._record_action(limiter, "192.168.1.1")
        assert self._check_limit_no_side_effect(limiter, "192.168.1.1") is True

    def test_independent_ips(self, limiter):
        """Different IPs are tracked independently."""
        # Fill quota for IP 1
        for _ in range(3):
            self._record_action(limiter, "10.0.0.1")

        assert self._check_limit_no_side_effect(limiter, "10.0.0.1") is True
        assert self._check_limit_no_side_effect(limiter, "10.0.0.2") is False

    def test_expiry(self, limiter):
        """Entries expire after window."""
        ip = "192.168.1.1"
        past_time = monotonic() - 20  # Window is 10

        # Inject old entries
        with limiter._lock:
            target_dict = limiter._requests
            target_dict[ip] = [past_time, past_time + 1, past_time + 2]

        # Should be pruned and allowed
        assert self._check_limit_no_side_effect(limiter, ip) is False

        with limiter._lock:
            # We injected 3 expired entries.
            # _check_limit_no_side_effect calls _prune.
            # So list should be empty.
            assert len(limiter._requests[ip]) == 0

    def test_get_retry_after(self, limiter):
        """Test retry_after calculation."""
        ip = "192.168.1.1"

        # Not limited -> 0
        assert limiter.get_retry_after(ip) == 0

        # Fill quota
        for _ in range(3):
            self._record_action(limiter, ip)

        # Limited -> > 0
        retry = limiter.get_retry_after(ip)
        assert retry > 0
        assert retry <= 10

    def test_thread_safety(self, limiter):
        """Basic thread safety check."""
        ip = "192.168.1.1"

        def worker():
            for _ in range(20):
                self._record_action(limiter, ip)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with limiter._lock:
            # We tried 80 actions.
            # For LoginRateLimiter: it just adds timestamps always (record_failure).
            # For Chat/Share (is_limited): it stops adding once limit is reached.
            # So Login will have 80, others will have 'max' (3).

            count = len(limiter._requests[ip])
            if isinstance(limiter, LoginRateLimiter):
                assert count == 80
            elif hasattr(limiter, "is_limited"):
                # Once limit is reached, is_limited returns True and DOES NOT add timestamp.
                # So it should be capped at max_requests (3)
                assert count == 3
            else:
                # Base class manual _add_timestamp calls
                assert count == 80
