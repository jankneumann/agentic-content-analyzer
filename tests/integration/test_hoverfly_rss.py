"""Integration tests for RSS ingestion via Hoverfly API simulation.

These tests verify that HTTP-level behaviors (status codes, headers, content
negotiation, error responses) work correctly through real HTTP calls routed
to Hoverfly's webserver, rather than using mocked httpx responses.

Requirements:
    - Hoverfly running: `make hoverfly-up`
    - Simulations in: tests/integration/fixtures/simulations/rss_feed.json

Run:
    make test-hoverfly
    # or: pytest tests/integration/test_hoverfly_rss.py -v
"""

from pathlib import Path

import httpx
import pytest

SIMULATIONS_DIR = Path(__file__).parent / "fixtures" / "simulations"


@pytest.mark.hoverfly
@pytest.mark.integration
class TestRSSFeedSimulation:
    """Test RSS feed fetching through Hoverfly simulated responses."""

    def test_fetch_valid_rss_feed(self, hoverfly, hoverfly_url):
        """Verify successful RSS feed fetch returns valid XML with items."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        response = httpx.get(f"{hoverfly_url}/feed")

        assert response.status_code == 200
        assert "application/rss+xml" in response.headers["content-type"]
        assert "<rss" in response.text
        assert "<item>" in response.text
        assert "Large Language Models: 2026 Update" in response.text
        assert "Vector Databases Compared" in response.text

    def test_fetch_empty_rss_feed(self, hoverfly, hoverfly_url):
        """Verify handling of RSS feed with no items."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        response = httpx.get(f"{hoverfly_url}/feed/empty")

        assert response.status_code == 200
        assert "<rss" in response.text
        assert "<item>" not in response.text

    def test_fetch_rss_feed_server_error(self, hoverfly, hoverfly_url):
        """Verify handling of HTTP 500 from feed server."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        response = httpx.get(f"{hoverfly_url}/feed/error")

        assert response.status_code == 500
        assert response.text == "Internal Server Error"

    def test_fetch_rss_feed_not_found(self, hoverfly, hoverfly_url):
        """Verify handling of HTTP 404 from feed server."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        response = httpx.get(f"{hoverfly_url}/feed/not-found")

        assert response.status_code == 404

    def test_rss_feed_content_type_header(self, hoverfly, hoverfly_url):
        """Verify Content-Type header is correctly returned for RSS."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        response = httpx.get(f"{hoverfly_url}/feed")

        content_type = response.headers["content-type"]
        assert "application/rss+xml" in content_type
        assert "charset=utf-8" in content_type


@pytest.mark.hoverfly
@pytest.mark.integration
class TestHoverflyClientManagement:
    """Test Hoverfly client management operations."""

    def test_health_check(self, hoverfly):
        """Verify Hoverfly health check works."""
        assert hoverfly.is_healthy()

    def test_import_and_count_pairs(self, hoverfly):
        """Verify simulation import and pair counting."""
        count = hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")
        assert count == 4  # 4 pairs in rss_feed.json

        loaded = hoverfly.get_simulation_pair_count()
        assert loaded == 4

    def test_reset_clears_simulations(self, hoverfly):
        """Verify reset removes all simulation pairs."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")
        assert hoverfly.get_simulation_pair_count() > 0

        hoverfly.reset_simulation()
        assert hoverfly.get_simulation_pair_count() == 0

    def test_export_simulation(self, hoverfly):
        """Verify simulation export returns valid structure."""
        hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")

        exported = hoverfly.export_simulation()
        assert "data" in exported
        assert "pairs" in exported["data"]
        assert len(exported["data"]["pairs"]) == 4

    def test_get_mode(self, hoverfly):
        """Verify mode reporting (should be simulate in webserver mode)."""
        mode = hoverfly.get_mode()
        assert mode == "simulate"

    def test_simulation_isolation_between_tests(self, hoverfly):
        """Verify simulations are reset between tests (fixture cleanup)."""
        # This test relies on the fixture's teardown resetting simulations.
        # If the previous test left simulations, this count would be > 0.
        count = hoverfly.get_simulation_pair_count()
        assert count == 0, "Simulations should be reset between tests"
