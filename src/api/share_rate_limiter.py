"""In-memory rate limiter for public share endpoints.

Limits requests to /shared/* by client IP to prevent abuse
and token enumeration. State resets on process restart.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from time import monotonic


class ShareRateLimiter:
    """Rate limiter for public share endpoints.

    Tracks requests per IP within a sliding window.
    Thread-safe via a lock.

    Args:
        max_requests: Maximum requests per window.
        window_seconds: Sliding window duration in seconds.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._max = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._request_count = 0

    def _prune(self, ip: str) -> None:
        """Remove expired entries for a given IP."""
        cutoff = monotonic() - self._window
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
        if not self._requests[ip]:
            del self._requests[ip]

    def _maybe_cleanup(self) -> None:
        """Periodically clean up all expired entries to prevent memory growth."""
        self._request_count += 1
        if self._request_count % 200 == 0:
            cutoff = monotonic() - self._window
            expired_ips = [
                ip for ip, times in self._requests.items() if all(t <= cutoff for t in times)
            ]
            for ip in expired_ips:
                del self._requests[ip]

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
            if len(self._requests.get(ip, [])) >= self._max:
                return True
            self._requests[ip].append(monotonic())
            return False

    def get_retry_after(self, ip: str) -> int:
        """Get seconds until the IP can make another request.

        Args:
            ip: Client IP address.

        Returns:
            Seconds until the oldest tracked request expires,
            or 0 if the IP is not limited.
        """
        with self._lock:
            self._prune(ip)
            requests = self._requests.get(ip, [])
            if len(requests) < self._max:
                return 0
            oldest = min(requests)
            remaining = self._window - (monotonic() - oldest)
            return max(1, int(remaining))


# Module-level singleton — 100 requests per minute per IP
share_rate_limiter = ShareRateLimiter(max_requests=100, window_seconds=60)
