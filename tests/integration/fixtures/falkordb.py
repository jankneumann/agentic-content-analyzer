"""FalkorDB Lite integration test fixtures.

Provides session-scoped FalkorDB Lite instance and function-scoped
graph reset for isolated test execution.
"""

from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


def _is_falkordb_lite_available() -> bool:
    """Check if falkordblite package is installed."""
    try:
        from redislite import FalkorDB  # noqa: F401

        return True
    except ImportError:
        return False


FALKORDB_LITE_AVAILABLE = _is_falkordb_lite_available()

requires_falkordb = pytest.mark.skipif(
    not FALKORDB_LITE_AVAILABLE,
    reason="falkordblite package not installed",
)


@pytest.fixture(scope="session")
def falkordb_lite():
    """Session-scoped embedded FalkorDB Lite instance.

    Starts once per test session, stops on teardown.
    """
    if not FALKORDB_LITE_AVAILABLE:
        pytest.skip("falkordblite package not installed")

    from tests.helpers.falkordb_lite import FalkorDBLiteFixture

    fixture = FalkorDBLiteFixture()
    fixture.start()
    yield fixture
    fixture.stop()


@pytest.fixture
def falkordb_graph(falkordb_lite):
    """Function-scoped FalkorDB graph with auto-reset.

    Clears all data before each test for isolation.
    """
    falkordb_lite.reset()
    return falkordb_lite.graph("test")


@pytest.fixture
def falkordb_provider(falkordb_lite):
    """Function-scoped FalkorDBGraphDBProvider backed by Lite.

    Clears all data before each test. Returns a real provider
    instance connected to the embedded FalkorDB.
    """
    falkordb_lite.reset()
    return falkordb_lite.create_provider(database="test")
