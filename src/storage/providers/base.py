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

    def get_queue_url(self) -> str:
        """Return connection URL for queue workers.

        Queue workers need direct connections (not pooled) because:
        - Long-lived processes exhaust pooler limits
        - LISTEN/NOTIFY requires direct connections
        - Workers should not compete with web request pool

        For local PostgreSQL, this is the same as get_engine_url().
        For cloud providers (Supabase, Neon), this returns the direct
        connection URL that bypasses the connection pooler.

        Returns:
            Direct connection URL suitable for queue workers
        """
        ...

    def get_queue_options(self) -> dict[str, Any]:
        """Return engine options optimized for queue workers.

        Queue workers typically need different configuration than web requests:
        - Larger pool size for background workers processing multiple jobs
        - Longer timeouts for long-running job processing
        - Different recycle intervals for persistent connections

        Returns:
            Engine configuration dictionary for queue workers
        """
        ...

    def supports_pg_cron(self) -> bool:
        """Check if this provider supports the pg_cron extension.

        pg_cron enables scheduled jobs to run directly in the database,
        independent of application worker uptime. This is useful for:
        - Scheduled data processing
        - Periodic cleanup tasks
        - Enqueueing jobs at specific times

        Returns:
            True if pg_cron is available, False otherwise
        """
        ...
