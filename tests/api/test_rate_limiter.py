"""Unit tests for the LoginRateLimiter class.

Tests cover:
- Blocking after max failures
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

from src.api.rate_limiter import LoginRateLimiter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def limiter():
    """Fresh limiter with short window for testing."""
    return LoginRateLimiter(max_attempts=3, window_seconds=10)


@pytest.fixture
def strict_limiter():
    """Limiter with very short window to test expiry."""
    return LoginRateLimiter(max_attempts=2, window_seconds=1)


# ===========================================================================
# Blocking Tests
# ===========================================================================


class TestBlocking:
    """Test that IPs get blocked after exceeding max attempts."""

    def test_not_blocked_initially(self, limiter):
        """A new IP is not blocked."""
        assert limiter.is_blocked("192.168.1.1") is False

    def test_not_blocked_under_limit(self, limiter):
        """IP is not blocked with fewer failures than the limit."""
        limiter.record_failure("192.168.1.1")
        limiter.record_failure("192.168.1.1")
        assert limiter.is_blocked("192.168.1.1") is False

    def test_blocked_at_limit(self, limiter):
        """IP is blocked after exactly max_attempts failures."""
        for _ in range(3):
            limiter.record_failure("192.168.1.1")
        assert limiter.is_blocked("192.168.1.1") is True

    def test_blocked_over_limit(self, limiter):
        """IP is still blocked with more failures than the limit."""
        for _ in range(5):
            limiter.record_failure("192.168.1.1")
        assert limiter.is_blocked("192.168.1.1") is True


# ===========================================================================
# Independent IP Tracking Tests
# ===========================================================================


class TestIndependentIPs:
    """Test that different IPs are tracked independently."""

    def test_different_ips_independent(self, limiter):
        """Failures from one IP don't affect another."""
        for _ in range(3):
            limiter.record_failure("10.0.0.1")

        assert limiter.is_blocked("10.0.0.1") is True
        assert limiter.is_blocked("10.0.0.2") is False

    def test_multiple_ips_tracked(self, limiter):
        """Multiple IPs can be blocked independently."""
        for _ in range(3):
            limiter.record_failure("10.0.0.1")
            limiter.record_failure("10.0.0.2")

        assert limiter.is_blocked("10.0.0.1") is True
        assert limiter.is_blocked("10.0.0.2") is True
        assert limiter.is_blocked("10.0.0.3") is False


# ===========================================================================
# Expiry Tests
# ===========================================================================


class TestExpiry:
    """Test that entries expire after the time window."""

    def test_entries_expire_after_window(self, limiter):
        """Old entries are pruned when the window has passed."""
        ip = "192.168.1.1"

        # Record failures with timestamps in the past (beyond the window)
        past_time = monotonic() - 20  # 20 seconds ago, window is 10
        with limiter._lock:
            limiter._attempts[ip] = [past_time, past_time + 1, past_time + 2]

        # After pruning, the IP should no longer be blocked
        assert limiter.is_blocked(ip) is False

    def test_partial_expiry(self, limiter):
        """Only old entries expire; recent ones persist."""
        ip = "192.168.1.1"
        now = monotonic()

        with limiter._lock:
            # 2 old entries (expired) + 1 recent
            limiter._attempts[ip] = [now - 20, now - 15, now - 1]

        # After pruning, only 1 recent attempt remains -> not blocked (need 3)
        assert limiter.is_blocked(ip) is False

    def test_expired_ip_cleaned_up(self, limiter):
        """Fully expired IPs are removed from the internal dict."""
        ip = "192.168.1.1"
        past_time = monotonic() - 20

        with limiter._lock:
            limiter._attempts[ip] = [past_time]

        # Trigger pruning via is_blocked
        limiter.is_blocked(ip)

        # The IP should be removed entirely
        with limiter._lock:
            assert ip not in limiter._attempts


# ===========================================================================
# Periodic Cleanup Tests
# ===========================================================================


class TestPeriodicCleanup:
    """Test the _maybe_cleanup periodic maintenance."""

    def test_cleanup_runs_every_100_requests(self, limiter):
        """Cleanup removes all expired IPs every 100 requests."""
        past_time = monotonic() - 20
        with limiter._lock:
            limiter._attempts["expired-ip"] = [past_time]
            limiter._request_count = 99  # Next call will be the 100th

        # This should trigger cleanup
        limiter.is_blocked("trigger-ip")

        with limiter._lock:
            assert "expired-ip" not in limiter._attempts

    def test_cleanup_keeps_active_entries(self, limiter):
        """Cleanup does not remove IPs with recent entries."""
        recent_time = monotonic() - 1
        past_time = monotonic() - 20

        with limiter._lock:
            limiter._attempts["active-ip"] = [recent_time]
            limiter._attempts["expired-ip"] = [past_time]
            limiter._request_count = 99

        limiter.is_blocked("trigger-ip")

        with limiter._lock:
            assert "active-ip" in limiter._attempts
            assert "expired-ip" not in limiter._attempts


# ===========================================================================
# get_retry_after Tests
# ===========================================================================


class TestGetRetryAfter:
    """Test the get_retry_after method."""

    def test_returns_zero_when_not_blocked(self, limiter):
        """Returns 0 if IP is not blocked."""
        assert limiter.get_retry_after("192.168.1.1") == 0

    def test_returns_zero_under_limit(self, limiter):
        """Returns 0 if failures are under the limit."""
        limiter.record_failure("192.168.1.1")
        assert limiter.get_retry_after("192.168.1.1") == 0

    def test_returns_positive_when_blocked(self, limiter):
        """Returns positive seconds when IP is blocked."""
        for _ in range(3):
            limiter.record_failure("192.168.1.1")

        retry_after = limiter.get_retry_after("192.168.1.1")
        assert retry_after > 0
        # Should be close to window_seconds (10) but not exceed it
        assert retry_after <= 10

    def test_returns_at_least_1(self, limiter):
        """Returns at least 1 second, never 0, when blocked."""
        for _ in range(3):
            limiter.record_failure("192.168.1.1")

        # Even if the oldest entry is very close to expiry, min is 1
        retry_after = limiter.get_retry_after("192.168.1.1")
        assert retry_after >= 1

    def test_retry_after_decreases_over_time(self, limiter):
        """retry_after should decrease as the oldest entry ages."""
        ip = "192.168.1.1"
        now = monotonic()

        # Set entries that are 5 seconds old (window=10, so 5 seconds remaining)
        with limiter._lock:
            limiter._attempts[ip] = [now - 5, now - 4, now - 3]

        retry_after = limiter.get_retry_after(ip)
        # Oldest is 5 sec old, window is 10 -> ~5 seconds left
        assert 3 <= retry_after <= 6


# ===========================================================================
# Thread Safety Tests
# ===========================================================================


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_failures(self):
        """Recording failures from multiple threads doesn't corrupt state."""
        limiter = LoginRateLimiter(max_attempts=100, window_seconds=60)
        ip = "192.168.1.1"

        def record_many():
            for _ in range(50):
                limiter.record_failure(ip)

        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 200 entries (4 threads * 50)
        with limiter._lock:
            assert len(limiter._attempts[ip]) == 200

    def test_concurrent_block_checks(self):
        """Checking is_blocked from multiple threads doesn't crash."""
        limiter = LoginRateLimiter(max_attempts=5, window_seconds=60)
        ip = "192.168.1.1"

        # Pre-populate some failures
        for _ in range(3):
            limiter.record_failure(ip)

        results = []

        def check_many():
            for _ in range(50):
                results.append(limiter.is_blocked(ip))

        threads = [threading.Thread(target=check_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All checks should return False (3 < 5)
        assert all(r is False for r in results)


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_unknown_ip_keyword(self):
        """The 'unknown' IP string works like any other."""
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=10)
        limiter.record_failure("unknown")
        limiter.record_failure("unknown")
        assert limiter.is_blocked("unknown") is True

    def test_empty_ip_string(self):
        """Empty string IP is handled without error."""
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=10)
        limiter.record_failure("")
        assert limiter.is_blocked("") is False
        limiter.record_failure("")
        assert limiter.is_blocked("") is True

    def test_zero_max_attempts_blocks_immediately(self):
        """With max_attempts=0, any IP is immediately blocked."""
        limiter = LoginRateLimiter(max_attempts=0, window_seconds=10)
        # Even without any failures recorded, is_blocked checks len >= 0 which is True
        assert limiter.is_blocked("192.168.1.1") is True

    def test_record_failure_prunes_old_entries(self):
        """record_failure prunes expired entries before adding new one."""
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=10)
        ip = "192.168.1.1"

        # Add an old entry
        old_time = monotonic() - 20
        with limiter._lock:
            limiter._attempts[ip] = [old_time, old_time + 1]

        # Record a new failure -- should prune old ones first
        limiter.record_failure(ip)

        with limiter._lock:
            # Old entries pruned, only the new one remains
            assert len(limiter._attempts[ip]) == 1
