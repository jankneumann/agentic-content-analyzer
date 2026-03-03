"""In-memory rate limiter for login endpoint.

Tracks failed login attempts per client IP with automatic expiry.
No external dependencies (no Redis). State resets on process restart.
"""

from __future__ import annotations

from src.api.rate_limiter_base import SlidingWindowRateLimiter


class LoginRateLimiter(SlidingWindowRateLimiter):
    """Rate limiter for login attempts.

    Tracks failed attempts per IP address within a sliding time window.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        super().__init__(max_requests=max_attempts, window_seconds=window_seconds)
        # Rename internal attribute for compatibility if needed, but base uses _requests.
        # Original code used self._attempts.
        # We can alias property if tests access _attempts directly, or update tests.
        # Looking at tests, they access _attempts. Let's use property or just map it.
        # Actually, let's keep it clean and update tests if they inspect internals.
        # The base class uses _requests.

    @property
    def _attempts(self) -> dict[str, list[float]]:
        """Alias for base class _requests to satisfy existing tests."""
        return self._requests

    @_attempts.setter
    def _attempts(self, value: dict[str, list[float]]) -> None:
        self._requests = value

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is currently rate-limited.

        Also prunes expired entries for the IP.

        Args:
            ip: Client IP address.

        Returns:
            True if the IP has exceeded the attempt limit.
        """
        with self._lock:
            self._prune(ip)
            self._maybe_cleanup()
            return self._is_limit_reached(ip)

    def record_failure(self, ip: str) -> None:
        """Record a failed login attempt for an IP.

        Args:
            ip: Client IP address.
        """
        with self._lock:
            self._prune(ip)
            self._add_timestamp(ip)


# Module-level singleton — shared across all requests in this process
login_rate_limiter = LoginRateLimiter()
