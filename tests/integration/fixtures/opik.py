"""Opik integration test fixtures.

Provides fixtures for testing Opik observability provider integration.
Requires Opik stack running (make opik-up).

Configuration via Settings (env vars):
- OPIK_BASE_URL: Opik UI/nginx proxy URL (default: http://localhost:5174)
- OPIK_BACKEND_URL: Opik backend URL for health checks (default: http://localhost:8080)
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import httpx
import pytest

from src.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Generator

# Derive Opik URLs from Settings (evaluated once at import time)
_settings = get_settings()
OPIK_BASE_URL = _settings.opik_base_url
OPIK_API_URL = _settings.opik_base_url  # API routes through UI proxy (same URL)
OPIK_BACKEND_URL = _settings.opik_backend_url
OPIK_OTLP_ENDPOINT = f"{OPIK_BASE_URL}/api/v1/private/otel"


def _opik_is_running() -> bool:
    """Check if Opik backend is healthy."""
    try:
        response = httpx.get(f"{OPIK_BACKEND_URL}/health-check", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _get_project_by_name(project_name: str) -> dict | None:
    """Get a project by name from Opik API.

    Uses the UI proxy which routes to the private API.
    """
    try:
        response = httpx.get(
            f"{OPIK_API_URL}/api/v1/private/projects",
            params={"name": project_name},
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json()
            projects = data.get("content", [])
            for project in projects:
                if project.get("name") == project_name:
                    result: dict = project
                    return result
        return None
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


def _get_traces_for_project(project_id: str, limit: int = 10) -> list[dict]:
    """Get traces for a project from Opik API.

    Uses GET /api/v1/private/traces with query parameters.
    The UI proxy routes to the private API.
    """
    try:
        response = httpx.get(
            f"{OPIK_API_URL}/api/v1/private/traces",
            params={
                "project_id": project_id,
                "page": 1,
                "size": limit,
            },
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json()
            traces: list[dict] = data.get("content", [])
            return traces
        return []
    except (httpx.ConnectError, httpx.TimeoutException):
        return []


def _delete_project(project_id: str) -> bool:
    """Delete a project from Opik.

    Uses the UI proxy which routes to the private API.
    """
    try:
        response = httpx.delete(
            f"{OPIK_API_URL}/api/v1/private/projects/{project_id}",
            timeout=5.0,
        )
        return response.status_code in (200, 204, 404)
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture
def opik_available() -> bool:
    """Check if Opik is available for testing."""
    return _opik_is_running()


# Pytest marker for tests that require Opik
requires_opik = pytest.mark.skipif(
    not _opik_is_running(),
    reason="Opik not running (start with: make opik-up)",
)


@pytest.fixture
def unique_project_name() -> str:
    """Generate unique project name for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


def _reset_otel_tracer_provider() -> None:
    """Reset OTel global tracer provider to allow re-initialization.

    The OTel SDK only allows setting the global tracer provider once.
    For testing, we need to reset it between tests to allow each test
    to have its own isolated provider.
    """
    try:
        from opentelemetry import trace

        # Reset the global state to allow re-initialization
        # This effectively "resets" the global tracer provider
        trace._TRACER_PROVIDER = None
        trace._TRACER_PROVIDER_SET_ONCE._done = False
    except (ImportError, AttributeError):
        pass  # OTel not installed or API changed


@pytest.fixture
def opik_provider(unique_project_name: str) -> Generator:
    """Create an OpikProvider configured for testing.

    Uses unique project name for isolation.
    Resets OTel global state before each test.
    Cleans up the project after test completes.
    """
    from src.telemetry.providers.opik import OpikProvider

    # Reset OTel global state to allow fresh provider
    _reset_otel_tracer_provider()

    provider = OpikProvider(
        endpoint=OPIK_OTLP_ENDPOINT,
        project_name=unique_project_name,
        service_name="newsletter-aggregator-test",
        log_prompts=True,
    )

    yield provider

    # Cleanup: flush any remaining spans
    provider.flush()
    provider.shutdown()

    # Give Opik time to process, then delete test project
    time.sleep(1)
    project = _get_project_by_name(unique_project_name)
    if project:
        _delete_project(project["id"])


class OpikTestHelpers:
    """Helper class for Opik test assertions."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self._project_id: str | None = None

    def wait_for_traces(
        self, expected_count: int = 1, timeout: float = 10.0, poll_interval: float = 0.5
    ) -> list[dict]:
        """Wait for traces to appear in Opik.

        Args:
            expected_count: Minimum number of traces to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            List of traces found

        Raises:
            TimeoutError: If traces don't appear within timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            project = _get_project_by_name(self.project_name)
            if project:
                self._project_id = project["id"]
                traces = _get_traces_for_project(project["id"])
                if len(traces) >= expected_count:
                    return traces
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Timed out waiting for {expected_count} traces in project '{self.project_name}'. "
            f"Found: {len(traces) if 'traces' in dir() else 0}"
        )

    def get_project_id(self) -> str | None:
        """Get the project ID (cached from wait_for_traces)."""
        if self._project_id:
            return self._project_id
        project = _get_project_by_name(self.project_name)
        if project:
            self._project_id = project["id"]
        return self._project_id


@pytest.fixture
def opik_test_helpers(unique_project_name: str) -> OpikTestHelpers:
    """Provide helper functions for Opik test assertions."""
    return OpikTestHelpers(unique_project_name)
