"""OTLP proxy endpoint for frontend trace export.

Forwards browser-originated OTLP trace data to the configured OTLP collector,
adding backend authentication headers server-side. This avoids CORS issues
and prevents exposing collector credentials in browser JavaScript.

Only active when OTel is enabled (OTEL_ENABLED=true).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from src.api.otel_rate_limiter import otel_proxy_rate_limiter
from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/otel", tags=["telemetry"])

# Maximum request body size: 1MB
MAX_BODY_SIZE = 1 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/x-protobuf",
}


@router.post("/v1/traces")
async def proxy_traces(request: Request) -> Response:
    """Forward OTLP trace data from the frontend to the OTLP collector.

    - Validates content-type (application/json or application/x-protobuf)
    - Rejects oversized payloads (>1MB)
    - Adds backend OTLP authentication headers
    - Returns 204 on success, 404 when disabled, 502 on upstream failure
    """
    if not settings.otel_enabled:
        return JSONResponse(status_code=404, content={"detail": "OTel is not enabled"})

    if not settings.otel_exporter_otlp_endpoint:
        return JSONResponse(status_code=503, content={"detail": "OTLP endpoint not configured"})

    client_ip = request.client.host if request.client else "unknown"
    if otel_proxy_rate_limiter.is_limited(client_ip):
        retry_after = otel_proxy_rate_limiter.get_retry_after(client_ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    # Validate content-type
    content_type = request.headers.get("content-type", "")
    # Normalize: strip parameters like charset
    base_content_type = content_type.split(";")[0].strip().lower()
    if base_content_type not in ALLOWED_CONTENT_TYPES:
        return JSONResponse(
            status_code=415,
            content={
                "detail": f"Unsupported content type: {content_type}. "
                f"Expected one of: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            },
        )

    # Check content-length before reading body
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large. Maximum size is {MAX_BODY_SIZE} bytes"},
            )
    except (ValueError, TypeError):
        pass  # Malformed content-length header; body size check below will catch it

    # Read body with size limit
    body = await request.body()
    if len(body) > MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": f"Payload too large. Maximum size is {MAX_BODY_SIZE} bytes"},
        )

    # Build upstream URL
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
    if not endpoint.endswith("/v1/traces"):
        upstream_url = f"{endpoint}/v1/traces"
    else:
        upstream_url = endpoint

    # Parse OTLP authentication headers from settings
    upstream_headers: dict[str, str] = {"content-type": content_type}
    if settings.otel_exporter_otlp_headers:
        for pair in settings.otel_exporter_otlp_headers.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                upstream_headers[key.strip()] = value.strip()

    # Add Opik project name header to route frontend traces to the correct project
    # This matches the header the backend Opik provider uses for direct traces
    if settings.opik_project_name:
        upstream_headers["projectName"] = settings.opik_project_name

    # Forward to OTLP collector
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                upstream_url,
                content=body,
                headers=upstream_headers,
            )

        if response.status_code >= 400:
            logger.warning(
                "OTLP collector returned %d: %s",
                response.status_code,
                response.text[:200],
            )
            return JSONResponse(
                status_code=502,
                content={"detail": "OTLP collector returned an error"},
            )

        return Response(status_code=204)

    except httpx.TimeoutException:
        logger.warning("OTLP collector request timed out")
        return JSONResponse(
            status_code=502,
            content={"detail": "OTLP collector request timed out"},
        )
    except Exception:
        logger.exception("Failed to forward traces to OTLP collector")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to forward traces to OTLP collector"},
        )
