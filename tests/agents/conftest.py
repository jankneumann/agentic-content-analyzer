"""External-boundary adapters for legacy agent unit tests."""

from __future__ import annotations

import pytest

from tests.clients.operational_runtime import install_operational_runtime


@pytest.fixture(autouse=True)
def legacy_agent_operational_adapters(monkeypatch: pytest.MonkeyPatch):
    """Exercise production scopes while replacing unavailable external systems."""
    return install_operational_runtime(monkeypatch)
