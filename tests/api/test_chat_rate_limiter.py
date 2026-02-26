"""Unit tests for the ChatRateLimiter class.

Tests cover:
- Limiting after max requests
- Independent tracking per IP
- Expiry of old entries after window passes
- Periodic cleanup of all expired entries
- get_retry_after returns correct remaining seconds
- Thread safety (basic concurrency check)
"""

from __future__ import annotations

import threading
from time import monotonic

import pytest

from src.api.chat_rate_limiter import ChatRateLimiter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def limiter():
    """Fresh limiter with short window for testing."""
    return ChatRateLimiter(max_requests=3, window_seconds=10)


# ===========================================================================
# Limiting Tests
# ===========================================================================


class TestLimiting:
    """Test that IPs get limited after exceeding max requests."""

    def test_not_limited_initially(self, limiter):
        """A new IP is not limited."""
        # First request
        assert limiter.is_limited("192.168.1.1") is False

    def test_not_limited_under_limit(self, limiter):
        """IP is not limited with fewer requests than the limit."""
        # max=3
        assert limiter.is_limited("192.168.1.1") is False  # 1st
        assert limiter.is_limited("192.168.1.1") is False  # 2nd
        assert limiter.is_limited("192.168.1.1") is False  # 3rd

    def test_limited_at_limit(self, limiter):
        """IP is limited after max_requests."""
        # max=3
        limiter.is_limited("192.168.1.1")  # 1
        limiter.is_limited("192.168.1.1")  # 2
        limiter.is_limited("192.168.1.1")  # 3

        # 4th request should be blocked
        assert limiter.is_limited("192.168.1.1") is True

    def test_limited_over_limit(self, limiter):
        """IP remains limited with more requests."""
        for _ in range(3):
            limiter.is_limited("192.168.1.1")

        assert limiter.is_limited("192.168.1.1") is True
        assert limiter.is_limited("192.168.1.1") is True


# ===========================================================================
# Independent IP Tracking Tests
# ===========================================================================


class TestIndependentIPs:
    """Test that different IPs are tracked independently."""

    def test_different_ips_independent(self, limiter):
        """Requests from one IP don't affect another."""
        for _ in range(3):
            limiter.is_limited("10.0.0.1")

        assert limiter.is_limited("10.0.0.1") is True
        assert limiter.is_limited("10.0.0.2") is False

    def test_multiple_ips_tracked(self, limiter):
        """Multiple IPs can be limited independently."""
        for _ in range(3):
            limiter.is_limited("10.0.0.1")
            limiter.is_limited("10.0.0.2")

        assert limiter.is_limited("10.0.0.1") is True
        assert limiter.is_limited("10.0.0.2") is True
        assert limiter.is_limited("10.0.0.3") is False


# ===========================================================================
# Expiry Tests
# ===========================================================================


class TestExpiry:
    """Test that entries expire after the time window."""

    def test_entries_expire_after_window(self, limiter):
        """Old entries are pruned when the window has passed."""
        ip = "192.168.1.1"

        # Record requests with timestamps in the past
        past_time = monotonic() - 20  # 20 seconds ago, window is 10
        with limiter._lock:
            limiter._requests[ip] = [past_time, past_time + 1, past_time + 2]

        # After pruning, the IP should no longer be limited
        assert limiter.is_limited(ip) is False

    def test_partial_expiry(self, limiter):
        """Only old entries expire; recent ones persist."""
        ip = "192.168.1.1"
        now = monotonic()

        with limiter._lock:
            # 2 old entries (expired) + 1 recent
            limiter._requests[ip] = [now - 20, now - 15, now - 1]

        # After pruning, only 1 recent request remains -> not limited (need 3)
        assert limiter.is_limited(ip) is False

        # But verify count is correct (should be 2 now after this call adds one)
        with limiter._lock:
            assert len(limiter._requests[ip]) == 2


# ===========================================================================
# Periodic Cleanup Tests
# ===========================================================================


class TestPeriodicCleanup:
    """Test the _maybe_cleanup periodic maintenance."""

    def test_cleanup_runs_every_100_requests(self, limiter):
        """Cleanup removes all expired IPs every 100 requests."""
        past_time = monotonic() - 20
        with limiter._lock:
            limiter._requests["expired-ip"] = [past_time]
            limiter._request_count = 99  # Next call will be the 100th

        # This should trigger cleanup
        limiter.is_limited("trigger-ip")

        with limiter._lock:
            assert "expired-ip" not in limiter._requests

    def test_cleanup_keeps_active_entries(self, limiter):
        """Cleanup does not remove IPs with recent entries."""
        recent_time = monotonic() - 1
        past_time = monotonic() - 20

        with limiter._lock:
            limiter._requests["active-ip"] = [recent_time]
            limiter._requests["expired-ip"] = [past_time]
            limiter._request_count = 99

        limiter.is_limited("trigger-ip")

        with limiter._lock:
            assert "active-ip" in limiter._requests
            assert "expired-ip" not in limiter._requests


# ===========================================================================
# get_retry_after Tests
# ===========================================================================


class TestGetRetryAfter:
    """Test the get_retry_after method."""

    def test_returns_zero_when_not_limited(self, limiter):
        """Returns 0 if IP is not limited."""
        assert limiter.get_retry_after("192.168.1.1") == 0

    def test_returns_zero_under_limit(self, limiter):
        """Returns 0 if requests are under the limit."""
        limiter.is_limited("192.168.1.1")
        assert limiter.get_retry_after("192.168.1.1") == 0

    def test_returns_positive_when_limited(self, limiter):
        """Returns positive seconds when IP is limited."""
        for _ in range(3):
            limiter.is_limited("192.168.1.1")

        retry_after = limiter.get_retry_after("192.168.1.1")
        assert retry_after > 0
        # Should be close to window_seconds (10) but not exceed it
        assert retry_after <= 10

    def test_returns_at_least_1(self, limiter):
        """Returns at least 1 second, never 0, when limited."""
        for _ in range(3):
            limiter.is_limited("192.168.1.1")

        retry_after = limiter.get_retry_after("192.168.1.1")
        assert retry_after >= 1


# ===========================================================================
# Thread Safety Tests
# ===========================================================================


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_requests(self):
        """Making requests from multiple threads doesn't corrupt state."""
        limiter = ChatRateLimiter(max_requests=1000, window_seconds=60)
        ip = "192.168.1.1"

        def make_many_requests():
            for _ in range(50):
                limiter.is_limited(ip)

        threads = [threading.Thread(target=make_many_requests) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 200 entries (4 threads * 50)
        # Note: is_limited adds a timestamp if not limited
        with limiter._lock:
            assert len(limiter._requests[ip]) == 200
