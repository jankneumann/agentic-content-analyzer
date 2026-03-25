"""In-memory rate limiter for OTLP trace proxy endpoint."""

from __future__ import annotations

from src.api.rate_limiter_base import EndpointRateLimiter

# Conservative default: max 60 requests/minute per client IP.
otel_proxy_rate_limiter = EndpointRateLimiter(max_requests=60, window_seconds=60)
