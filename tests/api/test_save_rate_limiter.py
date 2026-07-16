"""Tests for rate limiting on save-url and save-page endpoints.

Validates that the EndpointRateLimiter is correctly wired into both
content save endpoints with 30 req/min per IP.
"""

from src.api.rate_limiter_base import EndpointRateLimiter


class TestSaveRateLimiterSingleton:
    """Tests for the save_rate_limiter module-level singleton."""

    def test_save_rate_limiter_singleton_created(self):
        """Verify singleton has correct limits (30 req/min)."""
        from src.api.save_rate_limiter import save_rate_limiter

        assert isinstance(save_rate_limiter, EndpointRateLimiter)
        assert save_rate_limiter._max == 30
        assert save_rate_limiter._window == 60


class TestSaveRateLimiterUnit:
    """Unit tests for rate limiter logic applied to save endpoints."""

    def test_rate_limiter_allows_under_limit(self):
        """Requests under the limit are allowed."""
        limiter = EndpointRateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_limited("10.0.0.1") is False

    def test_rate_limiter_blocks_over_limit(self):
        """31st request is blocked after 30 allowed."""
        limiter = EndpointRateLimiter(max_requests=30, window_seconds=60)
        for _ in range(30):
            assert limiter.is_limited("10.0.0.1") is False

        assert limiter.is_limited("10.0.0.1") is True

    def test_rate_limiter_per_ip_isolation(self):
        """Different IPs have independent limits."""
        limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("10.0.0.1")

        assert limiter.is_limited("10.0.0.1") is True
        assert limiter.is_limited("10.0.0.2") is False

    def test_rate_limiter_retry_after_positive_when_blocked(self):
        """Retry-After returns a positive value when blocked."""
        limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("10.0.0.1")

        retry = limiter.get_retry_after("10.0.0.1")
        assert retry > 0
        assert retry <= 60

    def test_rate_limiter_retry_after_zero_when_not_blocked(self):
        """Retry-After returns 0 when not blocked."""
        limiter = EndpointRateLimiter(max_requests=10, window_seconds=60)
        assert limiter.get_retry_after("10.0.0.1") == 0
