"""In-memory rate limiter for content save endpoints.

Limits requests to /api/v1/content/save-url and /api/v1/content/save-page by client IP.
"""

from __future__ import annotations

from src.api.rate_limiter_base import EndpointRateLimiter

# Module-level singleton — 30 requests per minute per IP
save_rate_limiter = EndpointRateLimiter(max_requests=30, window_seconds=60)
