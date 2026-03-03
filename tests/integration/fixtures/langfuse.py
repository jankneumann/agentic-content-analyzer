"""Langfuse integration test fixtures.

Provides fixtures for testing Langfuse observability provider integration.
Requires Langfuse stack running (make langfuse-up).

Configuration via Settings (env vars):
- LANGFUSE_BASE_URL: Langfuse base URL (default: https://cloud.langfuse.com)
"""

from __future__ import annotations

import base64
import time
import uuid
from typing import TYPE_CHECKING

import httpx
import pytest

from src.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Generator

# Derive Langfuse URLs from Settings (evaluated once at import time)
_settings = get_settings()
LANGFUSE_BASE_URL = _settings.langfuse_base_url
LANGFUSE_OTLP_ENDPOINT = f"{LANGFUSE_BASE_URL}/api/public/otel"


def _langfuse_is_running() -> bool:
    """Check if Langfuse is healthy via /api/public/health."""
    try:
        response = httpx.get(f"{LANGFUSE_BASE_URL}/api/public/health", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _build_basic_auth() -> dict[str, str]:
    """Build Basic Auth header from settings for API access."""
    public_key = _settings.langfuse_public_key
    secret_key = _settings.langfuse_secret_key
    if not public_key or not secret_key:
        return {}

    credentials = f"{public_key}:{secret_key}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _get_traces(limit: int = 10) -> list[dict]:
    """Get traces from Langfuse API.

    Uses GET /api/public/traces with Basic Auth.
    """
    try:
        response = httpx.get(
            f"{LANGFUSE_BASE_URL}/api/public/traces",
            params={"limit": limit},
            headers=_build_basic_auth(),
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json()
            traces: list[dict] = data.get("data", [])
            return traces
        return []
    except (httpx.ConnectError, httpx.TimeoutException):
        return []


@pytest.fixture
def langfuse_available() -> bool:
    """Check if Langfuse is available for testing."""
    return _langfuse_is_running()


# Pytest marker for tests that require Langfuse
requires_langfuse = pytest.mark.skipif(
    not _langfuse_is_running(),
    reason="Langfuse not running (start with: make langfuse-up)",
)


@pytest.fixture
def unique_langfuse_project_name() -> str:
    """Generate unique project name for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


def _reset_otel_tracer_provider() -> None:
    """Reset OTel global tracer provider to allow re-initialization."""
    try:
        from opentelemetry import trace

        trace._TRACER_PROVIDER = None
        trace._TRACER_PROVIDER_SET_ONCE._done = False
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def langfuse_provider(unique_langfuse_project_name: str) -> Generator:
    """Create a LangfuseProvider configured for testing."""
    from src.telemetry.providers.langfuse import LangfuseProvider

    _reset_otel_tracer_provider()

    provider = LangfuseProvider(
        public_key=_settings.langfuse_public_key,
        secret_key=_settings.langfuse_secret_key,
        base_url=LANGFUSE_BASE_URL,
        service_name="newsletter-aggregator-test",
        log_prompts=True,
    )

    yield provider

    provider.flush()
    provider.shutdown()
    _reset_otel_tracer_provider()


class LangfuseTestHelpers:
    """Helper class for Langfuse test assertions."""

    def wait_for_traces(
        self,
        expected_count: int = 1,
        timeout: float = 15.0,
        poll_interval: float = 1.0,
    ) -> list[dict]:
        """Wait for traces to appear in Langfuse."""
        traces: list[dict] = []
        start = time.time()
        while time.time() - start < timeout:
            traces = _get_traces(limit=expected_count + 5)
            if len(traces) >= expected_count:
                return traces
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Timed out waiting for {expected_count} traces in Langfuse. Found: {len(traces)}"
        )


@pytest.fixture
def langfuse_test_helpers() -> LangfuseTestHelpers:
    """Provide helper functions for Langfuse test assertions."""
    return LangfuseTestHelpers()
