"""Hoverfly API simulation helper for integration tests.

Provides a client for managing Hoverfly simulations via the admin API (port 8888).
Hoverfly runs in webserver mode (port 8500), acting as a destination server that
returns pre-recorded responses based on request matching.

Usage:
    client = HoverflyClient()
    client.import_simulation("tests/integration/fixtures/simulations/rss_feed.json")
    # Now HTTP requests to http://localhost:8500 will return simulated responses

Architecture:
    - Port 8500: Webserver port (send HTTP requests here)
    - Port 8888: Admin API (manage simulations, check state)
    - Simulations: JSON files matching Hoverfly v5 schema
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Default Hoverfly endpoints (Docker Compose test profile)
DEFAULT_ADMIN_URL = "http://localhost:8888"
DEFAULT_PROXY_URL = "http://localhost:8500"


class HoverflyClient:
    """Client for Hoverfly admin API.

    Manages simulation lifecycle: import, export, reset, and health checks.
    """

    def __init__(
        self,
        admin_url: str = DEFAULT_ADMIN_URL,
        proxy_url: str = DEFAULT_PROXY_URL,
    ) -> None:
        self.admin_url = admin_url.rstrip("/")
        self.proxy_url = proxy_url.rstrip("/")
        self._client = httpx.Client(timeout=10.0)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> HoverflyClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def is_healthy(self) -> bool:
        """Check if Hoverfly is running and responsive."""
        try:
            resp = self._client.get(f"{self.admin_url}/api/v2/hoverfly")
            return resp.status_code == 200
        except httpx.TransportError:
            return False

    def get_mode(self) -> str:
        """Get current Hoverfly mode (simulate, capture, etc.)."""
        resp = self._client.get(f"{self.admin_url}/api/v2/hoverfly/mode")
        resp.raise_for_status()
        mode: str = resp.json()["mode"]
        return mode

    def set_mode(self, mode: str) -> None:
        """Set Hoverfly mode (simulate, capture, spy, diff)."""
        resp = self._client.put(
            f"{self.admin_url}/api/v2/hoverfly/mode",
            json={"mode": mode},
        )
        resp.raise_for_status()
        logger.info("Hoverfly mode set to: %s", mode)

    def import_simulation(self, path: str | Path) -> int:
        """Import a simulation JSON file into Hoverfly (replaces existing).

        Args:
            path: Path to a Hoverfly v5 simulation JSON file.

        Returns:
            Number of request/response pairs imported.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Simulation file not found: {path}")

        simulation = json.loads(path.read_text())
        resp = self._client.put(
            f"{self.admin_url}/api/v2/simulation",
            json=simulation,
        )
        resp.raise_for_status()

        pair_count = len(simulation.get("data", {}).get("pairs", []))
        logger.info("Imported %d simulation pairs from %s", pair_count, path.name)
        return pair_count

    def append_simulation(self, path: str | Path) -> int:
        """Append simulation pairs from a JSON file (keeps existing).

        Args:
            path: Path to a Hoverfly v5 simulation JSON file.

        Returns:
            Number of new request/response pairs appended.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Simulation file not found: {path}")

        simulation = json.loads(path.read_text())
        resp = self._client.post(
            f"{self.admin_url}/api/v2/simulation",
            json=simulation,
        )
        resp.raise_for_status()

        pair_count = len(simulation.get("data", {}).get("pairs", []))
        logger.info("Appended %d simulation pairs from %s", pair_count, path.name)
        return pair_count

    def export_simulation(self) -> dict:
        """Export current simulation state from Hoverfly.

        Returns:
            Hoverfly v5 simulation JSON as a dict.
        """
        resp = self._client.get(f"{self.admin_url}/api/v2/simulation")
        resp.raise_for_status()
        result: dict = resp.json()
        return result

    def reset_simulation(self) -> None:
        """Clear all simulations from Hoverfly."""
        resp = self._client.delete(f"{self.admin_url}/api/v2/simulation")
        resp.raise_for_status()
        logger.info("Hoverfly simulations reset")

    def get_simulation_pair_count(self) -> int:
        """Get number of request/response pairs currently loaded."""
        sim = self.export_simulation()
        return len(sim.get("data", {}).get("pairs", []))
