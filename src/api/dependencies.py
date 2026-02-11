import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config.settings import get_settings

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
