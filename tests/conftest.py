"""Root test configuration and shared fixtures.

This module provides:
- Factory Boy factories registered as pytest fixtures
- Database session fixtures with proper cleanup
- Common test utilities
- Environment isolation between tests

Factory Usage:
    Factories are registered as fixtures via pytest-factoryboy.
    Each factory is available as both:
    - `{model}_factory` - The factory class for building/creating
    - `{model}` - A single instance created by the factory

Examples:
    def test_with_content(content):
        # Uses auto-created Content instance
        assert content.id is not None

    def test_with_factory(content_factory):
        # Create multiple instances
        contents = content_factory.create_batch(5)
        assert len(contents) == 5

    def test_with_trait(content_factory):
        # Use traits
        pending = content_factory.create(pending=True)
        assert pending.status == ContentStatus.PENDING
"""

import os

import pytest
from pytest_factoryboy import register
from sqlalchemy.orm import sessionmaker

from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.podcast import PodcastFactory, PodcastScriptRecordFactory
from tests.factories.summary import SummaryFactory
from tests.helpers.test_db import create_test_engine, get_test_database_url

# =============================================================================
# Environment Isolation
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_environment():
    """Isolate environment variables between tests.

    This fixture snapshots the environment before each test and restores it
    after the test completes. This prevents test pollution where one test's
    environment modifications affect subsequent tests.

    Note: This uses yield-based cleanup which runs even if tests fail.
    For better isolation, tests should use monkeypatch.setenv() instead of
    directly modifying os.environ.
    """
    # Snapshot current environment
    original_env = os.environ.copy()

    yield

    # Restore original environment
    # First, remove any keys that were added during the test
    for key in list(os.environ.keys()):
        if key not in original_env:
            del os.environ[key]

    # Then restore any keys that were modified or removed
    for key, value in original_env.items():
        os.environ[key] = value


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the Settings singleton cache before and after each test.

    This ensures each test gets a fresh Settings instance and prevents
    cached settings from one test affecting another.
    """
    try:
        from src.config.settings import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass  # Settings module not available

    yield

    try:
        from src.config.settings import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass


# Register factories as fixtures
# This creates:
# - content_factory fixture (the factory class)
# - content fixture (single instance)
# - summary_factory, summary
# - digest_factory, digest
register(ContentFactory)
register(SummaryFactory)
register(DigestFactory)
register(PodcastScriptRecordFactory)
register(PodcastFactory)


# Worktree-aware test database URL (shared helper handles detection)
TEST_DATABASE_URL = get_test_database_url()


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine (session-scoped).

    Uses shared helper for worktree-aware DB naming and auto-creation.
    Tables are created fresh at the start and dropped at the end.
    """
    from src.models.audio_digest import AudioDigest  # noqa: F401
    from src.models.base import Base
    from src.models.content import Content  # noqa: F401
    from src.models.digest import Digest  # noqa: F401
    from src.models.podcast import Podcast, PodcastScriptRecord  # noqa: F401
    from src.models.settings import PromptOverride  # noqa: F401
    from src.models.summary import Summary  # noqa: F401
    from src.models.theme import ThemeAnalysis  # noqa: F401

    engine = create_test_engine(TEST_DATABASE_URL)

    # Drop all tables for clean state (handles interrupted runs)
    Base.metadata.drop_all(engine)
    # Create all tables fresh
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup after all tests
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Create a database session with transaction rollback.

    Each test gets an isolated session. All changes are rolled back
    after the test completes, ensuring test isolation.

    This fixture also configures Factory Boy to use this session
    for all model creation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    # Configure factories to use this session
    ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    PodcastScriptRecordFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    PodcastFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]

    yield session

    # Cleanup: Reset factory sessions, rollback transaction, close connection
    ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    DigestFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    PodcastScriptRecordFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    PodcastFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def content(db_session, content_factory):
    """Create a single Content instance using the factory.

    Uses db_session to ensure proper session binding.
    """
    return content_factory.create()


@pytest.fixture
def summary(db_session, summary_factory):
    """Create a single Summary instance using the factory.

    Uses db_session to ensure proper session binding.
    """
    return summary_factory.create()


@pytest.fixture
def digest(db_session, digest_factory):
    """Create a single Digest instance using the factory.

    Uses db_session to ensure proper session binding.
    """
    return digest_factory.create()


# =============================================================================
# Test Category Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Pure unit tests with no external dependencies")
    config.addinivalue_line("markers", "integration: Tests requiring database or external services")
    config.addinivalue_line("markers", "e2e: End-to-end API tests")
    config.addinivalue_line("markers", "slow: Tests that take >1s to complete")
    config.addinivalue_line("markers", "live_api: Tests that call real external APIs (costs money)")
    config.addinivalue_line(
        "markers", "hoverfly: Tests requiring Hoverfly API simulator (make hoverfly-up)"
    )
    config.addinivalue_line("markers", "crawl4ai: Tests requiring Crawl4AI setup")
    config.addinivalue_line(
        "markers", "neon: Tests requiring Neon database (NEON_API_KEY, NEON_PROJECT_ID)"
    )
