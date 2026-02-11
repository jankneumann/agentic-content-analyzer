import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config.settings import get_settings

# Endpoint authentication map — documents which routes are intentionally
# unauthenticated and why. This is the source of truth for route security.
# Enforcement can be added later if multi-user support is needed.
ENDPOINT_AUTH_MAP: dict[str, dict[str, str]] = {
    # System endpoints — infrastructure, no auth needed
    "/health": {"auth": "none", "reason": "Liveness probe for orchestrators"},
    "/ready": {"auth": "none", "reason": "Readiness probe for orchestrators"},
    "/api/v1/system/config": {"auth": "none", "reason": "Frontend feature flags"},
    "/api/v1/otel/v1/traces": {"auth": "none", "reason": "Frontend OTLP trace proxy"},
    # Content API — single-user model, instance is the security boundary
    "/api/v1/content/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/digests/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/summaries/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/themes/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/scripts/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/podcasts/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/audio-digests/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/chat/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/documents/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/files/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/sources/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/jobs/*": {"auth": "none", "reason": "Single-user model"},
    "/api/v1/save/*": {"auth": "none", "reason": "Content capture (extension/bookmarklet)"},
    # Admin endpoints — protected by X-Admin-Key header
    "/api/v1/settings/*": {"auth": "admin_api_key", "reason": "Prompt/settings management"},
    "/api/v1/prompts/*": {"auth": "admin_api_key", "reason": "Prompt management"},
}

# Define the API key header scheme
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verify_admin_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """
    Verify the admin API key.

    In development mode, settings endpoints are accessible without auth
    so the local UI works out of the box. In production, ADMIN_API_KEY
    must be set and requests must include the X-Admin-Key header.

    If ADMIN_API_KEY is set (even in dev), requests with the header are
    validated — this allows CLI/curl testing of auth without blocking
    the browser UI.

    Args:
        api_key: The API key from the X-Admin-Key header.

    Returns:
        The valid API key, or a sentinel string in dev mode.

    Raises:
        HTTPException: If the key is missing, invalid, or not configured.
    """
    settings = get_settings()

    # If a key was provided in the header, always validate it (any environment)
    if api_key and settings.admin_api_key:
        if not secrets.compare_digest(api_key, settings.admin_api_key):
            raise HTTPException(
                status_code=403,
                detail="Invalid admin API key",
            )
        return api_key

    # No header provided (or no key configured) — check environment
    if settings.is_development:
        # Dev mode: allow access without auth for local UI
        return "dev-no-auth"

    # Production/staging: require key
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=500,
            detail="Admin API key is not configured. Please set ADMIN_API_KEY environment variable.",
        )

    raise HTTPException(
        status_code=401,
        detail="Missing authentication header X-Admin-Key",
    )
