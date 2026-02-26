"""In-memory rate limiter for chat endpoints.

Limits requests to chat endpoints by client IP.
"""

from __future__ import annotations

from src.api.rate_limiter_base import EndpointRateLimiter

# Module-level singleton — 20 requests per minute per IP
chat_rate_limiter = EndpointRateLimiter(max_requests=20, window_seconds=60)
