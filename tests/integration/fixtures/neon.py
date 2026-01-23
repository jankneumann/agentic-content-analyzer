"""Neon integration test fixtures for ephemeral database branches.

These fixtures create isolated database branches for integration testing.
Each test module gets its own branch, which is automatically cleaned up.

Usage:
    @pytest.mark.asyncio
    async def test_with_neon_branch(neon_test_branch):
        # neon_test_branch is the connection string for an ephemeral branch
        engine = create_async_engine(neon_test_branch)
        # Run tests against isolated database...

Requirements:
    - NEON_API_KEY environment variable must be set
    - NEON_PROJECT_ID environment variable must be set
    - Optional: NEON_DEFAULT_BRANCH (defaults to "main")

Note:
    These fixtures are skipped if Neon credentials are not configured.
    This allows running other tests without Neon access.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from src.storage.providers.neon_branch import NeonBranchManager

# Check if Neon is configured
NEON_CONFIGURED = bool(os.environ.get("NEON_API_KEY") and os.environ.get("NEON_PROJECT_ID"))

# Skip reason for when Neon is not configured
SKIP_REASON = "Neon credentials not configured (NEON_API_KEY, NEON_PROJECT_ID required)"


def generate_branch_name(prefix: str = "test") -> str:
    """Generate a unique branch name for testing.

    Args:
        prefix: Branch name prefix (default: "test")

    Returns:
        Unique branch name like "test/abc12345"
    """
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}/{unique_id}"


@pytest.fixture(scope="session")
def neon_manager() -> NeonBranchManager | None:
    """Create a NeonBranchManager for the test session.

    Returns None if Neon is not configured, allowing tests to be skipped.
    """
    if not NEON_CONFIGURED:
        return None
    return NeonBranchManager()


@pytest_asyncio.fixture(scope="module")
async def neon_test_branch(
    neon_manager: NeonBranchManager | None,
) -> AsyncIterator[str]:
    """Create an ephemeral Neon branch for a test module.

    This fixture creates a new database branch at the start of the test module
    and deletes it when the module finishes. All tests in the module share
    the same branch for efficiency.

    Yields:
        PostgreSQL connection string for the test branch

    Skip:
        Skipped if NEON_API_KEY or NEON_PROJECT_ID are not set
    """
    if neon_manager is None:
        pytest.skip(SKIP_REASON)

    branch_name = generate_branch_name("test-module")

    async with neon_manager:
        async with neon_manager.branch_context(branch_name) as conn_str:
            yield conn_str


@pytest_asyncio.fixture(scope="function")
async def neon_isolated_branch(
    neon_manager: NeonBranchManager | None,
) -> AsyncIterator[str]:
    """Create an ephemeral Neon branch for a single test function.

    This fixture creates a new database branch for each test function,
    providing maximum isolation. Use this when tests modify the database
    and cannot share state.

    Yields:
        PostgreSQL connection string for the isolated test branch

    Skip:
        Skipped if NEON_API_KEY or NEON_PROJECT_ID are not set

    Note:
        This is slower than neon_test_branch since it creates a new
        branch for every test. Use sparingly for tests that truly
        require isolation.
    """
    if neon_manager is None:
        pytest.skip(SKIP_REASON)

    branch_name = generate_branch_name("test-isolated")

    async with neon_manager:
        async with neon_manager.branch_context(branch_name) as conn_str:
            yield conn_str


@pytest.fixture(scope="session")
def neon_available() -> bool:
    """Check if Neon is available for testing.

    Use this fixture to conditionally skip tests or test classes:

        @pytest.mark.skipif(not neon_available, reason="Neon not configured")
        def test_something():
            ...
    """
    return NEON_CONFIGURED


# Marker for tests that require Neon
requires_neon = pytest.mark.skipif(not NEON_CONFIGURED, reason=SKIP_REASON)
