"""Smoke test fixtures — httpx client against a live API server.

Usage:
    # Run with default BASE_URL (http://localhost:8000):
    pytest tests/smoke/ -m smoke -v

    # Run against a custom server:
    SMOKE_TEST_BASE_URL=https://staging.example.com pytest tests/smoke/ -m smoke -v

    # Include admin-protected endpoint tests:
    SMOKE_TEST_ADMIN_KEY=my-admin-key pytest tests/smoke/ -m smoke -v

Prerequisites:
    - API server running at BASE_URL (e.g., `make dev-bg`)
    - Database migrated (`alembic upgrade head`)
"""

import os

import httpx
import pytest

SMOKE_BASE_URL = os.getenv("SMOKE_TEST_BASE_URL", "http://localhost:8000")
SMOKE_ADMIN_KEY = os.getenv("SMOKE_TEST_ADMIN_KEY", os.getenv("ADMIN_API_KEY", ""))


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL of the live API server under test."""
    return SMOKE_BASE_URL


@pytest.fixture(scope="session")
def admin_key() -> str:
    """Admin API key for protected endpoint tests."""
    return SMOKE_ADMIN_KEY


@pytest.fixture(scope="session")
def http_client(base_url: str) -> httpx.Client:
    """Shared httpx client for smoke tests."""
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def admin_client(base_url: str, admin_key: str) -> httpx.Client:
    """httpx client with admin auth header pre-configured."""
    headers = {}
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    with httpx.Client(base_url=base_url, timeout=10.0, headers=headers) as client:
        yield client
