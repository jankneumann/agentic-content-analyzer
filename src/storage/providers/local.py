"""Local PostgreSQL database provider."""

from typing import Any

from sqlalchemy import Engine, text


class LocalPostgresProvider:
    """Provider for local PostgreSQL installations.

    This is the default provider for development and self-hosted deployments.
    It assumes PostgreSQL is running locally or on a private network.
    """

    def __init__(self, database_url: str) -> None:
        """Initialize local PostgreSQL provider.

        Args:
            database_url: PostgreSQL connection URL
        """
        self._database_url = database_url

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "local"

    def get_engine_url(self) -> str:
        """Return the database connection URL."""
        return self._database_url

    def get_engine_options(self) -> dict[str, Any]:
        """Return engine configuration for local PostgreSQL.

        Uses standard pool settings suitable for local development
        and self-hosted deployments.
        """
        return {
            "pool_pre_ping": True,  # Verify connections before use
            "pool_size": 10,  # Default pool size for local
            "max_overflow": 20,  # Allow burst connections
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "echo": False,  # Disable SQL logging
        }

    def health_check(self, engine: Engine) -> bool:
        """Check if local PostgreSQL is accessible.

        Args:
            engine: SQLAlchemy engine to check

        Returns:
            True if connection succeeds
        """
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_queue_url(self) -> str:
        """Return connection URL for queue workers.

        For local PostgreSQL, the queue URL is the same as the engine URL
        since there's no external connection pooler involved.

        Returns:
            Database connection URL
        """
        return self._database_url

    def get_queue_options(self) -> dict[str, Any]:
        """Return engine options optimized for queue workers.

        Queue workers processing background jobs may benefit from:
        - Larger pool for concurrent job processing
        - Longer timeouts for long-running jobs

        Returns:
            Engine configuration for queue workers
        """
        return {
            "pool_pre_ping": True,
            "pool_size": 20,  # Larger pool for workers
            "max_overflow": 10,
            "pool_recycle": 1800,  # 30 min recycle for persistent workers
            "pool_timeout": 60,  # Longer timeout for job processing
            "echo": False,
        }

    def supports_pg_cron(self) -> bool:
        """Check if pg_cron extension is available.

        Local PostgreSQL may have pg_cron installed manually, but it's
        not guaranteed. Return False as the default assumption.

        Returns:
            False (pg_cron requires manual installation on local PostgreSQL)
        """
        return False
