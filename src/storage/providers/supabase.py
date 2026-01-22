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
        """
        self._database_url = database_url
        self._project_ref = project_ref
        self._db_password = db_password
        self._region = region
        self._pooler_mode = pooler_mode
        self._az = az

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "supabase"

    def get_engine_url(self) -> str:
        """Return the Supabase connection URL.

        If a full URL was provided, returns it directly.
        Otherwise, constructs the URL from component parts.
        """
        if self._database_url:
            return self._database_url

        if not self._project_ref or not self._db_password:
            raise ValueError(
                "Supabase provider requires either database_url or "
                "both project_ref and db_password"
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
        - Supavisor connection pooling
        - Free tier connection limits
        - Required SSL connections
        - Appropriate timeouts for cloud latency
        """
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

        Returns:
            Direct URL if project_ref and password are available, None otherwise
        """
        if not self._project_ref or not self._db_password:
            return None

        # Direct connection URL (bypasses Supavisor)
        return (
            f"postgresql://postgres:{self._db_password}@"
            f"db.{self._project_ref}.supabase.co:5432/postgres"
        )
