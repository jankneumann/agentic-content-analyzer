"""In-memory rate limiter for login endpoint.

Tracks failed login attempts per client IP with automatic expiry.
No external dependencies (no Redis). State resets on process restart.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from time import monotonic


class LoginRateLimiter:
    """Rate limiter for login attempts.

    Tracks failed attempts per IP address within a sliding time window.
    Thread-safe via a lock (FastAPI may use multiple workers).

    Args:
        max_attempts: Maximum failed attempts before lockout.
        window_seconds: Time window in seconds for tracking attempts.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._max = max_attempts
        self._window = window_seconds
        self._lock = threading.Lock()
        self._request_count = 0

    def _prune(self, ip: str) -> None:
        """Remove expired entries for a given IP."""
        cutoff = monotonic() - self._window
        self._attempts[ip] = [t for t in self._attempts[ip] if t > cutoff]
        if not self._attempts[ip]:
            del self._attempts[ip]

    def _maybe_cleanup(self) -> None:
        """Periodically clean up all expired entries to prevent memory growth."""
        self._request_count += 1
        if self._request_count % 100 == 0:
            cutoff = monotonic() - self._window
            expired_ips = [
                ip for ip, times in self._attempts.items() if all(t <= cutoff for t in times)
            ]
            for ip in expired_ips:
                del self._attempts[ip]

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
            return len(self._attempts.get(ip, [])) >= self._max

    def record_failure(self, ip: str) -> None:
        """Record a failed login attempt for an IP.

        Args:
            ip: Client IP address.
        """
        with self._lock:
            self._prune(ip)
            self._attempts[ip].append(monotonic())

    def get_retry_after(self, ip: str) -> int:
        """Get seconds until the IP can retry.

        Args:
            ip: Client IP address.

        Returns:
            Seconds until the oldest tracked attempt expires,
            or 0 if the IP is not blocked.
        """
        with self._lock:
            self._prune(ip)
            attempts = self._attempts.get(ip, [])
            if len(attempts) < self._max:
                return 0
            oldest = min(attempts)
            remaining = self._window - (monotonic() - oldest)
            return max(1, int(remaining))


# Module-level singleton — shared across all requests in this process
login_rate_limiter = LoginRateLimiter()
