"""Hoverfly pytest fixtures for integration tests.

Provides fixtures for managing Hoverfly API simulations during integration tests.
Tests that use Hoverfly are automatically skipped if Hoverfly is not running.

Usage:
    @pytest.mark.hoverfly
    def test_rss_via_hoverfly(hoverfly, hoverfly_url):
        hoverfly.import_simulation("tests/integration/fixtures/simulations/rss_feed.json")
        response = httpx.get(f"{hoverfly_url}/feed")
        assert response.status_code == 200

Fixtures:
    - hoverfly_available: Session-scoped bool, True if Hoverfly is running
    - requires_hoverfly: Autouse marker that skips tests if Hoverfly is down
    - hoverfly: Function-scoped HoverflyClient (resets simulations after each test)
    - hoverfly_url: Base URL for sending HTTP requests to Hoverfly webserver
"""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest

from src.config.settings import get_settings
from tests.helpers.hoverfly import HoverflyClient

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def hoverfly_available() -> bool:
    """Check if Hoverfly is running (session-scoped).

    Returns True if Hoverfly admin API is reachable.
    URLs are read from Settings (HOVERFLY_ADMIN_URL env var).
    """
    settings = get_settings()
    with HoverflyClient(admin_url=settings.hoverfly_admin_url) as client:
        return client.is_healthy()


@pytest.fixture(autouse=True)
def requires_hoverfly(request: pytest.FixtureRequest, hoverfly_available: bool) -> None:
    """Skip tests marked with @pytest.mark.hoverfly if Hoverfly is not running.

    This fixture only activates for tests with the 'hoverfly' marker.
    Tests without the marker are unaffected.
    """
    if request.node.get_closest_marker("hoverfly"):
        if not hoverfly_available:
            pytest.skip("Hoverfly is not running (start with: make hoverfly-up)")


@pytest.fixture
def hoverfly(hoverfly_available: bool) -> Generator[HoverflyClient, None, None]:
    """Provide a HoverflyClient with automatic cleanup.

    Resets all simulations after each test to ensure isolation.
    The client connects to the admin API for simulation management.

    URLs are read from Settings (HOVERFLY_ADMIN_URL / HOVERFLY_PROXY_URL env vars).
    """
    if not hoverfly_available:
        pytest.skip("Hoverfly is not running (start with: make hoverfly-up)")

    settings = get_settings()
    client = HoverflyClient(
        admin_url=settings.hoverfly_admin_url,
        proxy_url=settings.hoverfly_proxy_url,
    )

    yield client

    # Cleanup: reset simulations after each test for isolation.
    # Suppress errors so a Hoverfly crash doesn't mask the real test failure.
    try:
        client.reset_simulation()
    except Exception:
        logger.warning("Failed to reset Hoverfly simulations during teardown", exc_info=True)
    finally:
        client.close()


@pytest.fixture
def hoverfly_url(hoverfly: HoverflyClient) -> str:
    """Base URL for HTTP requests to Hoverfly webserver.

    Use this URL as the base for httpx requests in tests:
        response = httpx.get(f"{hoverfly_url}/feed")

    URL is read from Settings (HOVERFLY_PROXY_URL env var).
    """
    return hoverfly.proxy_url
