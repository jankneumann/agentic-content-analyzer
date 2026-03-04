"""In-memory rate limiter for public share endpoints.

Limits requests to /shared/* by client IP.
"""

from __future__ import annotations

from src.api.rate_limiter_base import EndpointRateLimiter

# Module-level singleton — 100 requests per minute per IP
share_rate_limiter = EndpointRateLimiter(max_requests=100, window_seconds=60)
