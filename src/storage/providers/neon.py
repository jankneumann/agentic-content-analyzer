"""Neon cloud database provider."""

import re
from typing import Any

from sqlalchemy import Engine, text


class NeonProvider:
    """Provider for Neon serverless PostgreSQL.

    Neon uses connection pooling via PgBouncer with two URL formats:
    - Direct: ep-cool-darkness-123456.us-east-2.aws.neon.tech
    - Pooled: ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech

    The provider automatically handles URL conversion between pooled
    (for application use) and direct (for migrations) connections.
    """

    # Regex to parse Neon endpoint IDs and detect pooler suffix
    _ENDPOINT_PATTERN = re.compile(
        r"(ep-[a-z]+-[a-z]+-\d+)(-pooler)?\.([a-z0-9-]+)\.aws\.neon\.tech"
    )

    def __init__(
        self,
        *,
        database_url: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize Neon provider.

        Args:
            database_url: Full Neon connection URL
            project_id: Neon project ID (for API operations, informational)
            region: Region (auto-detected from URL if not set)
        """
        self._database_url = database_url
        self._project_id = project_id
        self._region = region

        # Auto-detect region from URL if not explicitly provided
        if self._database_url and not self._region:
            self._region = self._extract_region_from_url(self._database_url)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "neon"

    def _extract_region_from_url(self, url: str) -> str | None:
        """Extract the region from a Neon connection URL.

        Args:
            url: Neon database URL

        Returns:
            Region string (e.g., "us-east-2") or None if not found
        """
        match = self._ENDPOINT_PATTERN.search(url)
        if match:
            return match.group(3)
        return None

    def _is_pooled_url(self, url: str) -> bool:
        """Check if the URL is a pooled connection URL.

        Args:
            url: Neon database URL

        Returns:
            True if the URL contains -pooler suffix
        """
        return "-pooler." in url

    def _to_pooled_url(self, url: str) -> str:
        """Convert a direct URL to a pooled URL.

        Adds -pooler suffix after the endpoint ID if not already present.

        Args:
            url: Neon database URL

        Returns:
            URL with pooler suffix
        """
        if self._is_pooled_url(url):
            return url

        # Insert -pooler after the endpoint ID
        match = self._ENDPOINT_PATTERN.search(url)
        if match:
            endpoint_id = match.group(1)
            region = match.group(3)
            # Replace the hostname with pooled version
            direct_host = f"{endpoint_id}.{region}.aws.neon.tech"
            pooled_host = f"{endpoint_id}-pooler.{region}.aws.neon.tech"
            return url.replace(direct_host, pooled_host)

        # If pattern doesn't match, return original URL
        return url

    def _to_direct_url(self, url: str) -> str:
        """Convert a pooled URL to a direct URL.

        Removes -pooler suffix from the hostname if present.

        Args:
            url: Neon database URL

        Returns:
            URL without pooler suffix
        """
        if not self._is_pooled_url(url):
            return url

        # Remove -pooler suffix
        return url.replace("-pooler.", ".")

    def get_engine_url(self) -> str:
        """Return the Neon pooled connection URL.

        Automatically converts direct URLs to pooled URLs for
        optimal application performance with connection pooling.

        Returns:
            Pooled connection URL

        Raises:
            ValueError: If no database URL was provided
        """
        if not self._database_url:
            raise ValueError("Neon provider requires database_url")

        # Return pooled URL for application use
        return self._to_pooled_url(self._database_url)

    def get_direct_url(self) -> str:
        """Return direct connection URL for migrations.

        Migrations require direct connections, not pooled ones,
        to properly handle DDL statements and transactions.

        Returns:
            Direct connection URL (without -pooler suffix)

        Raises:
            ValueError: If no database URL was provided
        """
        if not self._database_url:
            raise ValueError("Neon provider requires database_url")

        return self._to_direct_url(self._database_url)

    def get_engine_options(self) -> dict[str, Any]:
        """Return engine configuration optimized for Neon.

        Configuration is tuned for:
        - Neon's PgBouncer connection pooling
        - Serverless cold start considerations
        - Required SSL connections
        - Appropriate timeouts for serverless latency
        """
        return {
            "pool_pre_ping": True,  # Essential for serverless connections
            "pool_size": 5,  # Conservative for Neon's connection limits
            "max_overflow": 2,  # Limited overflow due to connection limits
            "pool_recycle": 300,  # 5 min recycle for cloud connections
            "pool_timeout": 30,  # Longer timeout for serverless cold starts
            "echo": False,
            "connect_args": {
                "sslmode": "require",  # Neon requires SSL
                "options": "-c statement_timeout=30000",  # 30s query timeout
            },
        }

    def health_check(self, engine: Engine) -> bool:
        """Check if Neon connection is healthy.

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
