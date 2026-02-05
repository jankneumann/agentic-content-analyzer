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
    - Optional: NEON_DEFAULT_BRANCH (auto-detected if not set)

Note:
    These fixtures are skipped if Neon credentials are not configured.
    This allows running other tests without Neon access.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

# Load environment variables from .env file for tests
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables

from src.storage.providers.neon_branch import NeonBranchManager

# Check if Neon is configured (after loading .env)
NEON_CONFIGURED = bool(os.environ.get("NEON_API_KEY") and os.environ.get("NEON_PROJECT_ID"))

# Skip reason for when Neon is not configured
SKIP_REASON = "Neon credentials not configured (NEON_API_KEY, NEON_PROJECT_ID required)"

# Cache for detected default branch name
_detected_default_branch: str | None = None


def generate_branch_name(prefix: str = "test") -> str:
    """Generate a unique branch name for testing.

    Args:
        prefix: Branch name prefix (default: "test")

    Returns:
        Unique branch name like "test/abc12345"
    """
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}/{unique_id}"


async def _detect_default_branch(manager: NeonBranchManager) -> str:
    """Auto-detect the default branch (root branch without a parent).

    Args:
        manager: NeonBranchManager instance (must be in async context)

    Returns:
        Name of the root branch (e.g., "main", "production")

    Raises:
        RuntimeError: If no root branch is found
    """
    global _detected_default_branch

    # Return cached value if available
    if _detected_default_branch is not None:
        return _detected_default_branch

    # Check environment variable first
    env_branch = os.environ.get("NEON_DEFAULT_BRANCH")
    if env_branch:
        _detected_default_branch = env_branch
        return env_branch

    # Auto-detect by finding branch without a parent
    branches = await manager.list_branches()
    for branch in branches:
        if branch.parent_id is None:
            _detected_default_branch = branch.name
            return branch.name

    raise RuntimeError(
        "No root branch found in Neon project. Please set NEON_DEFAULT_BRANCH environment variable."
    )


@pytest.fixture(scope="function")
def neon_manager() -> NeonBranchManager | None:
    """Create a NeonBranchManager for a test.

    Returns None if Neon is not configured, allowing tests to be skipped.

    Note: This fixture is function-scoped because each test may need its
    own httpx client context.
    """
    if not NEON_CONFIGURED:
        return None
    return NeonBranchManager()


@pytest_asyncio.fixture(scope="module")
async def neon_test_branch() -> AsyncIterator[str]:
    """Create an ephemeral Neon branch for a test module.

    This fixture creates a new database branch at the start of the test module
    and deletes it when the module finishes. All tests in the module share
    the same branch for efficiency.

    The parent branch is auto-detected (the root branch without a parent).

    Yields:
        PostgreSQL connection string for the test branch

    Skip:
        Skipped if NEON_API_KEY or NEON_PROJECT_ID are not set
    """
    if not NEON_CONFIGURED:
        pytest.skip(SKIP_REASON)

    branch_name = generate_branch_name("test-module")
    manager = NeonBranchManager()

    async with manager:
        # Auto-detect the default branch
        default_branch = await _detect_default_branch(manager)
        async with manager.branch_context(branch_name, parent=default_branch) as conn_str:
            yield conn_str


@pytest_asyncio.fixture(scope="function")
async def neon_isolated_branch() -> AsyncIterator[str]:
    """Create an ephemeral Neon branch for a single test function.

    This fixture creates a new database branch for each test function,
    providing maximum isolation. Use this when tests modify the database
    and cannot share state.

    The parent branch is auto-detected (the root branch without a parent).

    Yields:
        PostgreSQL connection string for the isolated test branch

    Skip:
        Skipped if NEON_API_KEY or NEON_PROJECT_ID are not set

    Note:
        This is slower than neon_test_branch since it creates a new
        branch for every test. Use sparingly for tests that truly
        require isolation.
    """
    if not NEON_CONFIGURED:
        pytest.skip(SKIP_REASON)

    branch_name = generate_branch_name("test-isolated")
    manager = NeonBranchManager()

    async with manager:
        # Auto-detect the default branch
        default_branch = await _detect_default_branch(manager)
        async with manager.branch_context(branch_name, parent=default_branch) as conn_str:
            yield conn_str


@pytest_asyncio.fixture(scope="session")
async def neon_default_branch() -> str | None:
    """Get the name of the default (root) branch.

    Returns None if Neon is not configured.

    This is useful for tests that need to know the parent branch name.
    """
    if not NEON_CONFIGURED:
        return None

    manager = NeonBranchManager()
    async with manager:
        return await _detect_default_branch(manager)


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
