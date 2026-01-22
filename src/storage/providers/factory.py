"""Database provider factory with automatic detection."""

from typing import TYPE_CHECKING, Literal

from src.storage.providers.local import LocalPostgresProvider
from src.storage.providers.supabase import SupabaseProvider

if TYPE_CHECKING:
    from src.storage.providers.base import DatabaseProvider


def detect_provider(
    database_url: str,
    provider_override: Literal["local", "supabase"] | None = None,
    supabase_project_ref: str | None = None,
) -> Literal["local", "supabase"]:
    """Detect which database provider to use.

    Detection order:
    1. Explicit provider_override (if set)
    2. SUPABASE_PROJECT_REF env var present -> Supabase
    3. DATABASE_URL contains ".supabase." -> Supabase
    4. Default -> Local PostgreSQL

    Args:
        database_url: The database connection URL
        provider_override: Explicit provider selection
        supabase_project_ref: Supabase project reference if configured

    Returns:
        "local" or "supabase" indicating which provider to use
    """
    # 1. Explicit override takes precedence
    if provider_override:
        return provider_override

    # 2. Supabase project reference indicates Supabase provider
    if supabase_project_ref:
        return "supabase"

    # 3. URL contains Supabase domain
    if ".supabase." in database_url:
        return "supabase"

    # 4. Default to local PostgreSQL
    return "local"


def get_provider(
    database_url: str,
    *,
    provider_override: Literal["local", "supabase"] | None = None,
    supabase_project_ref: str | None = None,
    supabase_db_password: str | None = None,
    supabase_region: str = "us-east-1",
    supabase_pooler_mode: Literal["transaction", "session"] = "transaction",
    supabase_az: str = "0",
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

    Returns:
        DatabaseProvider implementation (LocalPostgresProvider or SupabaseProvider)

    Raises:
        ValueError: If Supabase is selected but required config is missing
    """
    provider_type = detect_provider(
        database_url=database_url,
        provider_override=provider_override,
        supabase_project_ref=supabase_project_ref,
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

    # Default: local PostgreSQL
    return LocalPostgresProvider(database_url=database_url)
