"""Shared fixtures for telemetry tests."""

from __future__ import annotations

import pytest

from src.telemetry.providers.noop import NoopProvider


@pytest.fixture
def noop_provider() -> NoopProvider:
    """Create a NoopProvider instance for testing."""
    return NoopProvider()
