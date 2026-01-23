"""Database provider factory with automatic detection."""

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
    """Detect which database provider to use.

    Detection order:
    1. Explicit provider_override (if set)
    2. SUPABASE_PROJECT_REF env var present -> Supabase
    3. NEON_PROJECT_ID env var present -> Neon
    4. DATABASE_URL contains ".supabase." -> Supabase
    5. DATABASE_URL contains ".neon.tech" -> Neon
    6. Default -> Local PostgreSQL

    Args:
        database_url: The database connection URL
        provider_override: Explicit provider selection
        supabase_project_ref: Supabase project reference if configured
        neon_project_id: Neon project ID if configured

    Returns:
        "local", "supabase", or "neon" indicating which provider to use
    """
    # 1. Explicit override takes precedence
    if provider_override:
        return provider_override

    # 2. Supabase project reference indicates Supabase provider
    if supabase_project_ref:
        return "supabase"

    # 3. Neon project ID indicates Neon provider
    if neon_project_id:
        return "neon"

    # 4. URL contains Supabase domain
    if ".supabase." in database_url:
        return "supabase"

    # 5. URL contains Neon domain
    if ".neon.tech" in database_url:
        return "neon"

    # 6. Default to local PostgreSQL
    return "local"


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
    """Get the appropriate database provider based on configuration.

    This factory function returns the correct provider implementation
    based on environment configuration and auto-detection.

    Args:
        database_url: Base database connection URL
        provider_override: Explicit provider selection (overrides auto-detection)
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
    provider_type = detect_provider(
        database_url=database_url,
        provider_override=provider_override,
        supabase_project_ref=supabase_project_ref,
        neon_project_id=neon_project_id,
    )

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
