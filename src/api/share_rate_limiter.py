"""In-memory rate limiter for public share endpoints.

Limits requests to /shared/* by client IP to prevent abuse
and token enumeration. State resets on process restart.
"""

from __future__ import annotations

from src.api.rate_limiter_base import SlidingWindowRateLimiter


class ShareRateLimiter(SlidingWindowRateLimiter):
    """Rate limiter for public share endpoints.

    Tracks requests per IP within a sliding window.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(max_requests=max_requests, window_seconds=window_seconds)

    def is_limited(self, ip: str) -> bool:
        """Check if an IP has exceeded the rate limit.

        Also records the current request if not limited.

        Args:
            ip: Client IP address.

        Returns:
            True if the IP should be rate-limited.
        """
        with self._lock:
            self._prune(ip)
            self._maybe_cleanup()
            if self._is_limit_reached(ip):
                return True
            self._add_timestamp(ip)
            return False


# Module-level singleton — 100 requests per minute per IP
share_rate_limiter = ShareRateLimiter(max_requests=100, window_seconds=60)
