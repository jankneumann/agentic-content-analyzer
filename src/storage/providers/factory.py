"""Database provider factory.

Provider selection is determined by the DATABASE_PROVIDER environment variable.
See src/config/settings.py for configuration and validation.
"""

import warnings
from typing import TYPE_CHECKING, Literal

from src.storage.providers.local import LocalPostgresProvider
from src.storage.providers.neon import NeonProvider
from src.storage.providers.supabase import SupabaseProvider

if TYPE_CHECKING:
    from src.storage.providers.base import DatabaseProvider


def detect_provider(
    database_url: str,
    provider_override: Literal["local", "supabase", "neon"] | None = None,
    supabase_project_ref: str | None = None,
    neon_project_id: str | None = None,
) -> Literal["local", "supabase", "neon"]:
    """Return the database provider type.

    .. deprecated::
        This function is deprecated. Use settings.database_provider directly.
        Provider selection should be explicit via DATABASE_PROVIDER env var.

    Args:
        database_url: The database connection URL (unused, kept for compatibility)
        provider_override: Explicit provider selection - use this
        supabase_project_ref: Deprecated, ignored
        neon_project_id: Deprecated, ignored

    Returns:
        The provider_override if set, otherwise "local"
    """
    # Warn if using implicit detection parameters
    if supabase_project_ref or neon_project_id:
        warnings.warn(
            "detect_provider() implicit detection via supabase_project_ref/neon_project_id "
            "is deprecated. Set DATABASE_PROVIDER explicitly in your environment.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Return explicit override or default to local
    return provider_override if provider_override else "local"


def get_provider(
    database_url: str,
    *,
    provider_override: Literal["local", "supabase", "neon"] | None = None,
    supabase_project_ref: str | None = None,
    supabase_db_password: str | None = None,
    supabase_region: str = "us-east-1",
    supabase_pooler_mode: Literal["transaction", "session"] = "transaction",
    supabase_az: str = "0",
    neon_project_id: str | None = None,
    neon_region: str | None = None,
) -> "DatabaseProvider":
    """Get the appropriate database provider based on explicit configuration.

    Provider selection is determined by the provider_override parameter,
    which should be set from settings.database_provider.

    Example:
        from src.config import settings
        provider = get_provider(
            database_url=settings.get_effective_database_url(),
            provider_override=settings.database_provider,
            ...
        )

    Args:
        database_url: Base database connection URL
        provider_override: Explicit provider selection (required for cloud providers)
        supabase_project_ref: Supabase project reference ID
        supabase_db_password: Supabase database password
        supabase_region: Supabase AWS region
        supabase_pooler_mode: Supabase connection pooling mode
        supabase_az: Supabase AWS availability zone (0, 1, etc.)
        neon_project_id: Neon project ID (for API operations)
        neon_region: Neon region (auto-detected from URL if not set)

    Returns:
        DatabaseProvider implementation (LocalPostgresProvider, SupabaseProvider, or NeonProvider)

    Raises:
        ValueError: If Supabase is selected but required config is missing
    """
    # Use explicit provider or default to local
    provider_type = provider_override or "local"

    if provider_type == "supabase":
        # Supabase can use either a full URL or component-based config
        if supabase_project_ref and supabase_db_password:
            # Use component-based configuration
            return SupabaseProvider(
                project_ref=supabase_project_ref,
                db_password=supabase_db_password,
                region=supabase_region,
                pooler_mode=supabase_pooler_mode,
                az=supabase_az,
            )
        elif ".supabase." in database_url:
            # Use the provided Supabase URL directly
            return SupabaseProvider(database_url=database_url)
        else:
            raise ValueError(
                "Supabase provider requires either:\n"
                "  1. SUPABASE_PROJECT_REF and SUPABASE_DB_PASSWORD, or\n"
                "  2. A Supabase DATABASE_URL containing '.supabase.'"
            )

    if provider_type == "neon":
        # Neon uses the database URL directly
        return NeonProvider(
            database_url=database_url,
            project_id=neon_project_id,
            region=neon_region,
        )

    # Default: local PostgreSQL
    return LocalPostgresProvider(database_url=database_url)
