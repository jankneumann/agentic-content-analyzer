"""Neon branch management for ephemeral database branches.

This module provides async branch management using the Neon API,
supporting operations like creating, deleting, and listing database branches.
Branches are useful for CI/CD workflows, preview environments, and testing.

Neon API Documentation: https://api-docs.neon.tech/
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Neon API configuration
NEON_API_BASE_URL = "https://console.neon.tech/api/v2"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0


class NeonBranch(BaseModel):
    """Represents a Neon database branch."""

    id: str = Field(description="Unique branch identifier")
    name: str = Field(description="Branch name")
    parent_id: str | None = Field(default=None, description="Parent branch ID")
    created_at: datetime = Field(description="Branch creation timestamp")
    connection_string: str | None = Field(
        default=None, description="PostgreSQL connection string for this branch"
    )


class NeonAPIError(Exception):
    """Exception raised for Neon API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(f"{message} (status: {status_code})")


class NeonRateLimitError(NeonAPIError):
    """Exception raised when Neon API rate limit is exceeded."""

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded", status_code=429)


class NeonBranchManager:
    """Manages Neon database branches via the Neon API.

    Provides async operations for creating, deleting, and listing branches.
    Includes automatic retry with exponential backoff for rate limiting.

    Example usage:
        manager = NeonBranchManager()

        # Create a branch
        branch = await manager.create_branch("feature-branch", parent="main")

        # Use the branch context manager for automatic cleanup
        async with manager.branch_context("test-branch") as conn_str:
            # Use conn_str to connect to the ephemeral branch
            pass  # Branch is automatically deleted on exit
    """

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
        default_branch: str = "main",
    ):
        """Initialize the Neon branch manager.

        Args:
            api_key: Neon API key. Falls back to NEON_API_KEY env var.
            project_id: Neon project ID. Falls back to NEON_PROJECT_ID env var.
            default_branch: Default parent branch name. Falls back to
                NEON_DEFAULT_BRANCH env var or "main".
        """
        self._api_key = api_key or os.environ.get("NEON_API_KEY")
        self._project_id = project_id or os.environ.get("NEON_PROJECT_ID")
        self._default_branch = (
            default_branch
            if default_branch != "main"
            else os.environ.get("NEON_DEFAULT_BRANCH", "main")
        )
        self._client: httpx.AsyncClient | None = None
        self._owns_client = True

    def _validate_config(self) -> None:
        """Validate that required configuration is present."""
        if not self._api_key:
            raise ValueError(
                "Neon API key is required. Set NEON_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        if not self._project_id:
            raise ValueError(
                "Neon project ID is required. Set NEON_PROJECT_ID environment variable "
                "or pass project_id to constructor."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._validate_config()
            self._client = httpx.AsyncClient(
                base_url=NEON_API_BASE_URL,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "NeonBranchManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with exponential backoff retry on rate limits.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            url: Request URL (relative to base URL)
            **kwargs: Additional arguments passed to httpx request

        Returns:
            httpx.Response object

        Raises:
            NeonAPIError: For non-recoverable API errors
            NeonRateLimitError: If rate limit is still exceeded after all retries
        """
        client = await self._get_client()
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, url, **kwargs)

                if response.status_code == 429:
                    # Rate limited - extract retry-after if available
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after else backoff

                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            f"Rate limited by Neon API, retrying in {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{MAX_RETRIES})"
                        )
                        await asyncio.sleep(wait_time)
                        backoff = min(backoff * 2, MAX_BACKOFF)
                        continue
                    else:
                        raise NeonRateLimitError(retry_after=wait_time)

                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_data = response.json()
                        error_message = error_data.get("message", error_body)
                    except Exception:
                        error_message = error_body

                    raise NeonAPIError(error_message, status_code=response.status_code)

                return response

            except httpx.TimeoutException as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Request timeout, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise NeonAPIError(f"Request timed out: {e}") from e

            except httpx.RequestError as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Request error, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise NeonAPIError(f"Request failed: {e}") from e

        # Should not reach here, but just in case
        raise NeonAPIError("Max retries exceeded")

    async def _get_branch_id_by_name(self, name: str) -> str | None:
        """Get a branch ID by its name.

        Args:
            name: Branch name to look up

        Returns:
            Branch ID if found, None otherwise
        """
        branches = await self.list_branches()
        for branch in branches:
            if branch.name == name:
                return branch.id
        return None

    async def create_branch(
        self,
        name: str,
        parent: str = "main",
        *,
        from_timestamp: datetime | None = None,
        from_lsn: str | None = None,
    ) -> NeonBranch:
        """Create a new database branch.

        Args:
            name: Name for the new branch
            parent: Name of the parent branch (defaults to "main")
            from_timestamp: Optional timestamp to branch from (point-in-time recovery)
            from_lsn: Optional Log Sequence Number to branch from

        Returns:
            NeonBranch object representing the created branch

        Raises:
            NeonAPIError: If branch creation fails
            ValueError: If both from_timestamp and from_lsn are provided
        """
        if from_timestamp and from_lsn:
            raise ValueError("Cannot specify both from_timestamp and from_lsn")

        # Resolve parent branch name to ID
        parent_name = parent if parent != "main" else self._default_branch
        parent_id = await self._get_branch_id_by_name(parent_name)
        if not parent_id:
            raise NeonAPIError(f"Parent branch '{parent_name}' not found")

        # Build request payload
        payload: dict[str, Any] = {
            "branch": {
                "name": name,
                "parent_id": parent_id,
            },
            "endpoints": [
                {
                    "type": "read_write",
                }
            ],
        }

        # Add point-in-time recovery options if specified
        if from_timestamp:
            payload["branch"]["parent_timestamp"] = from_timestamp.isoformat()
        elif from_lsn:
            payload["branch"]["parent_lsn"] = from_lsn

        logger.info(f"Creating Neon branch '{name}' from parent '{parent_name}'")

        response = await self._request_with_retry(
            "POST",
            f"/projects/{self._project_id}/branches",
            json=payload,
        )

        data = response.json()
        branch_data = data.get("branch", {})
        branch_id = branch_data["id"]

        # Extract connection string from the response
        # The create branch API returns connection_uris directly
        connection_string = None
        endpoints = data.get("endpoints", [])

        # Wait for endpoint to become active before returning connection string
        # This ensures the database is ready to accept connections
        if endpoints:
            endpoint = endpoints[0]
            endpoint_id = endpoint.get("id")
            await self._wait_for_endpoint_ready(endpoint_id)

        connection_uris = data.get("connection_uris", [])
        if connection_uris:
            connection_string = connection_uris[0].get("connection_uri")
        elif endpoints:
            # Fallback: build connection string manually
            connection_string = await self._build_connection_string(
                endpoint_id, branch_id=branch_id, pooled=True
            )

        branch = NeonBranch(
            id=branch_data["id"],
            name=branch_data["name"],
            parent_id=branch_data.get("parent_id"),
            created_at=datetime.fromisoformat(branch_data["created_at"].replace("Z", "+00:00")),
            connection_string=connection_string,
        )

        logger.info(f"Created Neon branch '{name}' with ID {branch.id}")
        return branch

    async def delete_branch(self, name: str) -> None:
        """Delete a database branch.

        Args:
            name: Name of the branch to delete

        Raises:
            NeonAPIError: If branch deletion fails or branch not found
        """
        branch_id = await self._get_branch_id_by_name(name)
        if not branch_id:
            raise NeonAPIError(f"Branch '{name}' not found", status_code=404)

        logger.info(f"Deleting Neon branch '{name}' (ID: {branch_id})")

        await self._request_with_retry(
            "DELETE",
            f"/projects/{self._project_id}/branches/{branch_id}",
        )

        logger.info(f"Deleted Neon branch '{name}'")

    async def list_branches(self) -> list[NeonBranch]:
        """List all branches in the project.

        Returns:
            List of NeonBranch objects
        """
        response = await self._request_with_retry(
            "GET",
            f"/projects/{self._project_id}/branches",
        )

        data = response.json()
        branches = []

        for branch_data in data.get("branches", []):
            branches.append(
                NeonBranch(
                    id=branch_data["id"],
                    name=branch_data["name"],
                    parent_id=branch_data.get("parent_id"),
                    created_at=datetime.fromisoformat(
                        branch_data["created_at"].replace("Z", "+00:00")
                    ),
                )
            )

        return branches

    async def _get_branch_roles(self, branch_id: str) -> list[dict[str, Any]]:
        """Get all roles for a specific branch.

        Args:
            branch_id: The branch ID to get roles for

        Returns:
            List of role data dictionaries
        """
        response = await self._request_with_retry(
            "GET",
            f"/projects/{self._project_id}/branches/{branch_id}/roles",
        )
        data = response.json()
        roles: list[dict[str, Any]] = data.get("roles", [])
        return roles

    async def _wait_for_endpoint_ready(
        self, endpoint_id: str, max_wait_seconds: float = 60.0, poll_interval: float = 2.0
    ) -> None:
        """Wait for an endpoint to become active.

        Neon endpoints take a few seconds to become ready after creation.
        This method polls the endpoint status until it's active or times out.

        Args:
            endpoint_id: The endpoint ID to wait for
            max_wait_seconds: Maximum time to wait (default 60 seconds)
            poll_interval: Time between status checks (default 2 seconds)

        Raises:
            NeonAPIError: If endpoint doesn't become ready within timeout
        """
        import time

        start_time = time.monotonic()

        while (time.monotonic() - start_time) < max_wait_seconds:
            try:
                response = await self._request_with_retry(
                    "GET",
                    f"/projects/{self._project_id}/endpoints/{endpoint_id}",
                )
                data = response.json()
                endpoint = data.get("endpoint", {})
                current_state = endpoint.get("current_state")

                if current_state == "active":
                    logger.debug(f"Endpoint {endpoint_id} is now active")
                    return

                logger.debug(f"Endpoint {endpoint_id} state: {current_state}, waiting...")
                await asyncio.sleep(poll_interval)

            except NeonAPIError as e:
                if e.status_code == 404:
                    # Endpoint might not be created yet, keep waiting
                    logger.debug(f"Endpoint {endpoint_id} not found yet, waiting...")
                    await asyncio.sleep(poll_interval)
                else:
                    raise

        raise NeonAPIError(
            f"Endpoint {endpoint_id} did not become active within {max_wait_seconds}s",
            status_code=408,
        )

    async def _build_connection_string(
        self,
        endpoint_id: str,
        branch_id: str,
        pooled: bool = True,
        database_name: str = "neondb",
        role_name: str | None = None,
    ) -> str:
        """Build a connection string for a branch endpoint.

        Args:
            endpoint_id: Endpoint ID to get connection string for
            branch_id: Branch ID (used to look up roles)
            pooled: Whether to use connection pooling (default True)
            database_name: Name of the database (default "neondb")
            role_name: Database role name (auto-detected if not provided)

        Returns:
            PostgreSQL connection string
        """
        # Auto-detect role name if not provided
        if role_name is None:
            roles = await self._get_branch_roles(branch_id)
            if roles:
                # Use the first available role (usually the owner role)
                role_name = roles[0].get("name", "neondb_owner")
            else:
                role_name = "neondb_owner"  # Default fallback

        params = {
            "pooled": str(pooled).lower(),
            "endpoint_id": endpoint_id,
            "database_name": database_name,
            "role_name": role_name,
        }

        response = await self._request_with_retry(
            "GET",
            f"/projects/{self._project_id}/connection_uri",
            params=params,
        )

        data = response.json()
        uri: str = data["uri"]
        return uri

    async def get_connection_string(self, branch: str, pooled: bool = True) -> str:
        """Get the connection string for a branch.

        Args:
            branch: Branch name
            pooled: Whether to use connection pooling (default True)

        Returns:
            PostgreSQL connection string

        Raises:
            NeonAPIError: If branch not found or connection string unavailable
        """
        branch_id = await self._get_branch_id_by_name(branch)
        if not branch_id:
            raise NeonAPIError(f"Branch '{branch}' not found", status_code=404)

        # Get endpoints for this branch
        response = await self._request_with_retry(
            "GET",
            f"/projects/{self._project_id}/branches/{branch_id}/endpoints",
        )

        data = response.json()
        endpoints = data.get("endpoints", [])

        if not endpoints:
            raise NeonAPIError(f"No endpoints found for branch '{branch}'", status_code=404)

        # Get connection string for the first endpoint
        endpoint_id = endpoints[0]["id"]

        # Wait for endpoint to become active before getting connection string
        await self._wait_for_endpoint_ready(endpoint_id)

        return await self._build_connection_string(endpoint_id, branch_id=branch_id, pooled=pooled)

    @asynccontextmanager
    async def branch_context(self, name: str, parent: str | None = None) -> AsyncIterator[str]:
        """Create a temporary branch and clean it up on exit.

        This context manager creates a branch on entry and automatically
        deletes it on exit, making it ideal for CI/CD workflows and tests.

        Args:
            name: Name for the temporary branch
            parent: Parent branch name (defaults to the configured default branch)

        Yields:
            Connection string for the created branch

        Example:
            async with manager.branch_context("test-run-123") as conn_str:
                # Use conn_str to connect and run tests
                await run_tests(conn_str)
            # Branch is automatically deleted
        """
        parent_branch = parent or self._default_branch
        branch = await self.create_branch(name, parent=parent_branch)

        try:
            # Ensure we have a connection string
            if branch.connection_string:
                yield branch.connection_string
            else:
                conn_str = await self.get_connection_string(name)
                yield conn_str
        finally:
            try:
                await self.delete_branch(name)
            except Exception as e:
                logger.error(f"Failed to delete branch '{name}' during cleanup: {e}")
                # Re-raise if it's not a "not found" error (branch may have been
                # deleted by another process)
                if not isinstance(e, NeonAPIError) or e.status_code != 404:
                    raise
