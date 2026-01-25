"""Supabase cloud database provider."""

from typing import Any, Literal

from sqlalchemy import Engine, text


class SupabaseProvider:
    """Provider for Supabase cloud PostgreSQL.

    Supabase uses Supavisor for connection pooling with two modes:
    - Transaction mode (port 6543): More efficient, recommended for most use cases
    - Session mode (port 5432): Required for prepared statements

    The provider automatically configures SQLAlchemy for optimal
    performance with Supabase's connection pooler.

    Local Development Mode:
    - When local=True, connects to local Supabase at 127.0.0.1:54322
    - No SSL required for local connections
    - Uses postgres:postgres credentials
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        project_ref: str | None = None,
        db_password: str | None = None,
        region: str = "us-east-1",
        pooler_mode: Literal["transaction", "session"] = "transaction",
        az: str = "0",
        local: bool = False,
    ) -> None:
        """Initialize Supabase provider.

        Can be configured with either a full database URL or component parts.

        Args:
            database_url: Complete Supabase connection URL (if provided, ignores other params)
            project_ref: Supabase project reference ID
            db_password: Database password
            region: AWS region for the Supabase project
            pooler_mode: Connection pooling mode ("transaction" or "session")
            az: AWS availability zone number (found in Supabase connection string as aws-{az}-{region})
            local: Whether to use local Supabase (127.0.0.1:54322)
        """
        self._database_url = database_url
        self._project_ref = project_ref
        self._db_password = db_password
        self._region = region
        self._pooler_mode = pooler_mode
        self._az = az
        self._local = local

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "supabase"

    @property
    def is_local(self) -> bool:
        """Check if using local Supabase mode."""
        return self._local

    def get_engine_url(self) -> str:
        """Return the Supabase connection URL.

        If local mode, returns local connection URL.
        If a full URL was provided, returns it directly.
        Otherwise, constructs the URL from component parts.
        """
        # Local Supabase mode
        if self._local:
            return "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

        if self._database_url:
            return self._database_url

        if not self._project_ref or not self._db_password:
            raise ValueError(
                "Supabase provider requires either database_url or "
                "both project_ref and db_password "
                "(or set local=True for local development)"
            )

        # Transaction mode uses port 6543, session mode uses 5432
        port = 6543 if self._pooler_mode == "transaction" else 5432

        return (
            f"postgresql://postgres.{self._project_ref}:"
            f"{self._db_password}@"
            f"aws-{self._az}-{self._region}.pooler.supabase.com:"
            f"{port}/postgres"
        )

    def get_engine_options(self) -> dict[str, Any]:
        """Return engine configuration optimized for Supabase.

        Configuration is tuned for:
        - Supavisor connection pooling (cloud)
        - Free tier connection limits
        - Required SSL connections (cloud only)
        - Appropriate timeouts for cloud latency

        Local mode uses simpler configuration without SSL.
        """
        if self._local:
            # Local Supabase configuration - no SSL, shorter timeouts
            return {
                "pool_pre_ping": True,
                "pool_size": 5,
                "max_overflow": 5,
                "pool_recycle": 300,
                "pool_timeout": 10,  # Shorter timeout for local
                "echo": False,
                "connect_args": {
                    "options": "-c statement_timeout=30000",  # 30s query timeout
                },
            }

        # Cloud Supabase configuration
        return {
            "pool_pre_ping": True,  # Essential for cloud connections
            "pool_size": 5,  # Conservative for Supabase free tier
            "max_overflow": 2,  # Limited overflow due to connection limits
            "pool_recycle": 300,  # 5 min recycle for cloud connections
            "pool_timeout": 30,  # Longer timeout for cloud latency
            "echo": False,
            "connect_args": {
                "sslmode": "require",  # Supabase requires SSL
                "options": "-c statement_timeout=30000",  # 30s query timeout
            },
        }

    def health_check(self, engine: Engine) -> bool:
        """Check if Supabase connection is healthy.

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

    def get_direct_url(self) -> str | None:
        """Return direct connection URL for migrations (bypasses pooler).

        Alembic migrations require direct database connections, not pooled ones.
        Users should set SUPABASE_DIRECT_URL for migration operations.

        For local mode, returns the local connection URL (same as pooled).

        Returns:
            Direct URL if project_ref and password are available, None otherwise
        """
        # Local Supabase uses direct connection
        if self._local:
            return "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

        if not self._project_ref or not self._db_password:
            return None

        # Direct connection URL (bypasses Supavisor)
        return (
            f"postgresql://postgres:{self._db_password}@"
            f"db.{self._project_ref}.supabase.co:5432/postgres"
        )

    def get_queue_url(self) -> str:
        """Return connection URL for queue workers.

        Queue workers need direct connections (not pooled) because:
        - Long-lived processes exhaust Supavisor pooler limits
        - LISTEN/NOTIFY requires direct connections
        - Workers should not compete with web request pool

        Returns:
            Direct connection URL (bypasses Supavisor)

        Raises:
            ValueError: If direct URL cannot be constructed
        """
        direct_url = self.get_direct_url()
        if direct_url is None:
            raise ValueError(
                "Supabase queue URL requires either local=True or "
                "both project_ref and db_password"
            )
        return direct_url

    def get_queue_options(self) -> dict[str, Any]:
        """Return engine options optimized for queue workers.

        Queue workers processing background jobs benefit from:
        - Larger pool for concurrent job processing
        - Longer timeouts for long-running jobs
        - SSL required for cloud connections

        Returns:
            Engine configuration for queue workers
        """
        if self._local:
            return {
                "pool_pre_ping": True,
                "pool_size": 10,  # Larger pool for workers
                "max_overflow": 5,
                "pool_recycle": 1800,  # 30 min recycle
                "pool_timeout": 60,  # Longer timeout for job processing
                "echo": False,
            }

        return {
            "pool_pre_ping": True,
            "pool_size": 10,  # Larger pool for workers
            "max_overflow": 5,
            "pool_recycle": 600,  # 10 min recycle for cloud
            "pool_timeout": 60,  # Longer timeout for job processing
            "echo": False,
            "connect_args": {
                "sslmode": "require",
            },
        }

    def supports_pg_cron(self) -> bool:
        """Check if pg_cron extension is available.

        Supabase provides pg_cron as a built-in extension that can be
        enabled in the dashboard or via SQL: CREATE EXTENSION pg_cron;

        Returns:
            True (pg_cron is available on Supabase)
        """
        return True
