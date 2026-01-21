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
