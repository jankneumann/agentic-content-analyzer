"""In-memory rate limiter for chat endpoints.

Limits requests to chat endpoints by client IP to prevent abuse
and manage LLM costs. State resets on process restart.
"""

from __future__ import annotations

from src.api.rate_limiter_base import SlidingWindowRateLimiter


class ChatRateLimiter(SlidingWindowRateLimiter):
    """Rate limiter for chat endpoints.

    Tracks requests per IP within a sliding window.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60) -> None:
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


# Module-level singleton — 20 requests per minute per IP
chat_rate_limiter = ChatRateLimiter(max_requests=20, window_seconds=60)
