"""Railway cloud database provider."""

from typing import Any

from sqlalchemy import Engine, text

from src.config import settings


class RailwayProvider:
    """Provider for Railway PostgreSQL with custom extensions.

    Railway provides PostgreSQL as a service with automatic provisioning,
    connection pooling, and SSL enforcement. This provider is designed to
    work with a custom PostgreSQL image that includes extensions:
    - pgvector: Vector similarity search
    - pg_search: Full-text search (ParadeDB)
    - pgmq: Message queue
    - pg_cron: Job scheduling

    Railway connection model:
    - Internal: postgresql://user:pass@service.railway.internal:5432/railway
    - External: postgresql://user:pass@proxy.railway.app:PORT/railway

    Connection settings are optimized for Railway's Hobby plan (512 MB RAM)
    by default, but can be adjusted via environment variables for Pro/Enterprise.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
    ) -> None:
        """Initialize Railway provider.

        Args:
            database_url: Full Railway connection URL. If not provided,
                         uses RAILWAY_DATABASE_URL or DATABASE_URL from settings.
        """
        self._database_url = database_url

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "railway"

    def get_engine_url(self) -> str:
        """Return the Railway connection URL.

        Railway provides connection URLs via environment variables:
        - DATABASE_URL: Internal connection (for services on Railway)
        - DATABASE_PUBLIC_URL: External connection (via TCP proxy)

        For services running on Railway, the internal URL provides
        lower latency connections via the private network.

        Returns:
            Connection URL

        Raises:
            ValueError: If no database URL was provided
        """
        if not self._database_url:
            raise ValueError(
                "Railway provider requires database_url. "
                "Set DATABASE_URL or RAILWAY_DATABASE_URL in your environment."
            )

        return self._database_url

    def get_engine_options(self) -> dict[str, Any]:
        """Return engine configuration optimized for Railway.

        Configuration is tuned for:
        - Railway's connection handling (SSL required)
        - Hobby plan resource limits (512 MB RAM by default)
        - Serverless considerations (pre-ping for connection validation)

        Pool sizes can be adjusted via environment variables:
        - RAILWAY_POOL_SIZE: Number of connections in the pool
        - RAILWAY_MAX_OVERFLOW: Additional connections allowed beyond pool_size

        Returns:
            Engine configuration dictionary
        """
        # Use settings for pool configuration (allows Hobby/Pro/Enterprise tuning)
        pool_size: int = settings.railway_pool_size  # type: ignore[attr-defined]
        max_overflow: int = settings.railway_max_overflow  # type: ignore[attr-defined]
        pool_recycle: int = settings.railway_pool_recycle  # type: ignore[attr-defined]
        pool_timeout: int = settings.railway_pool_timeout  # type: ignore[attr-defined]

        return {
            "pool_pre_ping": True,  # Validate connections before use
            "pool_size": pool_size,  # Default: 3 for Hobby plan
            "max_overflow": max_overflow,  # Default: 2 for Hobby plan
            "pool_recycle": pool_recycle,  # 5 min recycle for cloud connections
            "pool_timeout": pool_timeout,  # 30 second timeout
            "echo": False,
            "connect_args": {
                "sslmode": "require",  # Railway enforces SSL
                "options": "-c statement_timeout=30000",  # 30s query timeout
            },
        }

    def health_check(self, engine: Engine) -> bool:
        """Check if Railway connection is healthy.

        Verifies SSL connectivity and basic query execution.

        Args:
            engine: SQLAlchemy engine to check

        Returns:
            True if connection succeeds
        """
        try:
            with engine.connect() as conn:
                # Simple query to verify connectivity
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_queue_url(self) -> str:
        """Return connection URL for queue workers.

        Railway doesn't use a separate pooler like Supabase/Neon,
        so queue workers can use the same URL as the application.
        However, direct connections are preferred for workers.

        Returns:
            Connection URL for queue workers

        Raises:
            ValueError: If no database URL was provided
        """
        return self.get_engine_url()

    def get_queue_options(self) -> dict[str, Any]:
        """Return engine options optimized for queue workers.

        Queue workers processing background jobs benefit from:
        - Larger pool for concurrent job processing
        - Longer timeouts for long-running jobs
        - SSL required for Railway connections

        Returns:
            Engine configuration for queue workers
        """
        # Workers can use slightly larger pools
        pool_size: int = settings.railway_pool_size + 2  # type: ignore[attr-defined]
        max_overflow: int = settings.railway_max_overflow + 3  # type: ignore[attr-defined]

        return {
            "pool_pre_ping": True,
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_recycle": 600,  # 10 min recycle for workers
            "pool_timeout": 60,  # Longer timeout for long jobs
            "echo": False,
            "connect_args": {
                "sslmode": "require",
                # No statement_timeout for workers — jobs can be long-running
            },
        }

    def supports_pg_cron(self) -> bool:
        """Check if pg_cron extension is available.

        When using the custom Railway PostgreSQL image, pg_cron
        is included and enabled by default. This can be disabled
        via RAILWAY_PG_CRON_ENABLED=false if using the standard
        Railway PostgreSQL image.

        Returns:
            True if pg_cron is enabled in settings
        """
        return bool(settings.railway_pg_cron_enabled)  # type: ignore[attr-defined]

    def supports_pgvector(self) -> bool:
        """Check if pgvector extension is available.

        When using the custom Railway PostgreSQL image, pgvector
        is included for vector similarity search operations.

        Returns:
            True if pgvector is enabled in settings
        """
        return bool(settings.railway_pgvector_enabled)  # type: ignore[attr-defined]

    def supports_pg_search(self) -> bool:
        """Check if pg_search (ParadeDB) extension is available.

        When using the custom Railway PostgreSQL image, pg_search
        is included for full-text search with BM25 ranking.

        Returns:
            True if pg_search is enabled in settings
        """
        return bool(settings.railway_pg_search_enabled)  # type: ignore[attr-defined]

    def supports_pgmq(self) -> bool:
        """Check if pgmq extension is available.

        When using the custom Railway PostgreSQL image, pgmq
        is included for lightweight message queue operations.

        Returns:
            True if pgmq is enabled in settings
        """
        return bool(settings.railway_pgmq_enabled)  # type: ignore[attr-defined]
