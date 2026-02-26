"""Base class for in-memory sliding window rate limiting.

Provides common logic for tracking requests/failures per IP within a time window.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from time import monotonic


class SlidingWindowRateLimiter:
    """Base rate limiter using a sliding window.

    Tracks timestamps per IP address. Thread-safe.

    Args:
        max_requests: Maximum allowed entries per window.
        window_seconds: Time window duration in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._max = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._request_count = 0

    def _prune(self, ip: str) -> None:
        """Remove expired entries for a given IP.

        Must be called within a lock.
        """
        cutoff = monotonic() - self._window
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
        if not self._requests[ip]:
            del self._requests[ip]

    def _maybe_cleanup(self) -> None:
        """Periodically clean up all expired entries to prevent memory growth.

        Must be called within a lock.
        """
        self._request_count += 1
        if self._request_count % 100 == 0:
            cutoff = monotonic() - self._window
            expired_ips = [
                ip for ip, times in self._requests.items() if all(t <= cutoff for t in times)
            ]
            for ip in expired_ips:
                del self._requests[ip]

    def _add_timestamp(self, ip: str) -> None:
        """Add a current timestamp for the IP.

        Must be called within a lock.
        """
        self._requests[ip].append(monotonic())

    def _is_limit_reached(self, ip: str) -> bool:
        """Check if limit is reached for the IP.

        Must be called within a lock. Assumes _prune() has been called.
        """
        return len(self._requests.get(ip, [])) >= self._max

    def get_retry_after(self, ip: str) -> int:
        """Get seconds until the IP can make another request/attempt.

        Args:
            ip: Client IP address.

        Returns:
            Seconds until the oldest tracked entry expires,
            or 0 if the IP is not limited/blocked.
        """
        with self._lock:
            self._prune(ip)
            requests = self._requests.get(ip, [])
            if len(requests) < self._max:
                return 0
            oldest = min(requests)
            remaining = self._window - (monotonic() - oldest)
            return max(1, int(remaining))


class EndpointRateLimiter(SlidingWindowRateLimiter):
    """Standard rate limiter for API endpoints.

    Combines check and record logic: if limit not reached, records the request.
    """

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
