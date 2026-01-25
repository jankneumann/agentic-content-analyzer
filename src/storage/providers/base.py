"""Base database provider protocol."""

from typing import Any, Protocol

from sqlalchemy import Engine


class DatabaseProvider(Protocol):
    """Protocol for database providers.

    Each provider implementation handles the specifics of connecting to
    a particular PostgreSQL hosting solution (local, Supabase, etc.)
    while exposing a consistent interface to the application.
    """

    @property
    def name(self) -> str:
        """Return the provider name identifier."""
        ...

    def get_engine_url(self) -> str:
        """Return the SQLAlchemy connection URL for this provider."""
        ...

    def get_engine_options(self) -> dict[str, Any]:
        """Return provider-specific engine configuration options.

        These options are passed to create_engine() to configure
        connection pooling, SSL, timeouts, etc.
        """
        ...

    def health_check(self, engine: Engine) -> bool:
        """Verify database connectivity.

        Args:
            engine: SQLAlchemy engine to check

        Returns:
            True if connection is healthy, False otherwise
        """
        ...
