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

    Args:
        api_key: The API key from the X-Admin-Key header.

    Returns:
        The valid API key.

    Raises:
        HTTPException: If the key is missing, invalid, or not configured.
    """
    # Get settings dynamically to support testing with different env vars
    settings = get_settings()

    if not settings.admin_api_key:
        # Fail secure: if no admin key is configured, deny access to sensitive endpoints
        raise HTTPException(
            status_code=500,
            detail="Admin API key is not configured. Please set ADMIN_API_KEY environment variable.",
        )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication header X-Admin-Key",
        )

    if not secrets.compare_digest(api_key, settings.admin_api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key",
        )

    return api_key
