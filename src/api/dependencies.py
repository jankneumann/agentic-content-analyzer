import secrets

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.config.settings import get_settings

# Endpoint authentication map — documents which routes require auth and why.
# After Phase 1 owner auth, ALL endpoints are protected by AuthMiddleware
# (session cookie OR X-Admin-Key) except explicitly exempted paths.
# The verify_admin_key dependency on admin endpoints is retained as defense-in-depth.
ENDPOINT_AUTH_MAP: dict[str, dict[str, str]] = {
    # Exempt — no auth required (handled by AuthMiddleware exempt list)
    "/health": {"auth": "none", "reason": "Liveness probe for orchestrators"},
    "/ready": {"auth": "none", "reason": "Readiness probe for orchestrators"},
    "/api/v1/system/config": {
        "auth": "none",
        "reason": "Frontend feature flags (no sensitive data)",
    },
    "/api/v1/otel/v1/traces": {"auth": "none", "reason": "Frontend OTLP trace proxy"},
    "/api/v1/auth/*": {"auth": "none", "reason": "Login/logout/session endpoints"},
    # Protected — session cookie OR X-Admin-Key (enforced by AuthMiddleware)
    "/api/v1/contents/*": {"auth": "session_or_admin_key", "reason": "Content management"},
    "/api/v1/digests/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/summaries/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/themes/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/scripts/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/podcasts/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/audio-digests/*": {
        "auth": "session_or_admin_key",
        "reason": "Protected by middleware",
    },
    "/api/v1/chat/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/documents/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/files/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/sources/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/jobs/*": {"auth": "session_or_admin_key", "reason": "Protected by middleware"},
    "/api/v1/save/*": {"auth": "session_or_admin_key", "reason": "Content capture"},
    "/api/v1/*/share": {
        "auth": "session_or_admin_key",
        "reason": "Share management (enable/disable/status)",
    },
    # Public — no auth required (token-gated, rate-limited)
    "/shared/*": {"auth": "none", "reason": "Public shared content (token-gated, rate-limited)"},
    # Admin endpoints — session/admin_key (middleware) + verify_admin_key (defense-in-depth)
    "/api/v1/settings/*": {"auth": "admin_api_key", "reason": "Prompt/settings management"},
    "/api/v1/prompts/*": {"auth": "admin_api_key", "reason": "Prompt management"},
    "/api/v1/voice/*": {"auth": "admin_api_key", "reason": "Voice cleanup (LLM cost)"},
}

# Define the API key header scheme
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verify_admin_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str:
    """
    Verify the admin API key or session cookie.

    Accepts both X-Admin-Key header (CLI/extensions) and session cookies
    (browser/mobile) as valid authentication. In development mode,
    endpoints are accessible without auth so the local UI works out of
    the box.

    If ADMIN_API_KEY is set (even in dev), requests with the header are
    validated — this allows CLI/curl testing of auth without blocking
    the browser UI.

    Args:
        request: The incoming HTTP request (for cookie access).
        api_key: The API key from the X-Admin-Key header.

    Returns:
        The valid API key, or a sentinel string for session/dev auth.

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

    # Check session cookie (browser/mobile authentication)
    if settings.app_secret_key:
        from src.api.auth_routes import _COOKIE_NAME, _verify_jwt

        token = request.cookies.get(_COOKIE_NAME)
        if token:
            payload = _verify_jwt(token, settings.app_secret_key)
            if payload is not None:
                return "session-auth"

    # No header provided (or no key configured) — check environment
    if settings.is_development:
        # Check if keys are configured. If so, fail auth instead of bypassing.
        # This ensures that if a user sets a password, it is enforced even in dev.
        if settings.app_secret_key or settings.admin_api_key:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
            )

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
        detail="Please log in or provide X-Admin-Key header.",
    )
