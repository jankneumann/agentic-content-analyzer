"""Crawl4AI pytest fixtures for integration tests.

Provides fixtures for testing against a running Crawl4AI Docker server.
Tests that use Crawl4AI are automatically skipped if the server is not running.

Usage:
    @pytest.mark.crawl4ai
    def test_js_extraction(crawl4ai_url):
        response = httpx.post(f"{crawl4ai_url}/md", json={"url": "https://example.com"})
        assert response.status_code == 200

Fixtures:
    - crawl4ai_available: Session-scoped bool, True if Crawl4AI server is running
    - requires_crawl4ai: Autouse marker that skips tests if server is down
    - crawl4ai_url: Base URL for sending requests to Crawl4AI server
"""

from __future__ import annotations

import logging

import pytest

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_CRAWL4AI_DEFAULT_URL = "http://localhost:11235"


def _is_configured() -> bool:
    """Check if Crawl4AI server is configured and reachable."""
    import httpx

    settings = get_settings()
    url = settings.crawl4ai_server_url or _CRAWL4AI_DEFAULT_URL

    try:
        response = httpx.get(f"{url}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


CONFIGURED = _is_configured()


@pytest.fixture(scope="session")
def crawl4ai_available() -> bool:
    """Check if Crawl4AI server is running (session-scoped)."""
    return CONFIGURED


@pytest.fixture(autouse=True)
def requires_crawl4ai(request: pytest.FixtureRequest, crawl4ai_available: bool) -> None:
    """Skip tests marked with @pytest.mark.crawl4ai if server is not running."""
    if request.node.get_closest_marker("crawl4ai"):
        if not crawl4ai_available:
            pytest.skip("Crawl4AI server not available — start with: make crawl4ai-up")


@pytest.fixture(scope="session")
def crawl4ai_url() -> str:
    """Base URL for the Crawl4AI server."""
    settings = get_settings()
    return settings.crawl4ai_server_url or _CRAWL4AI_DEFAULT_URL
