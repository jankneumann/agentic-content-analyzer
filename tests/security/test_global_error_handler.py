"""Security tests for global error handler.

Tests that the global error handler does not leak sensitive information
in error responses.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.error_handler import register_error_handlers


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up required environment variables for tests.

    Uses monkeypatch to ensure proper cleanup after each test.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GRAPHITI_URL", "http://localhost:8080")
    monkeypatch.setenv("GRAPHITI_API_KEY", "test-key")


def test_global_error_handler_leakage():
    """Test that the global error handler does not leak sensitive information.

    Verifies that after the fix, sensitive data is not exposed in error responses.
    """
    app = FastAPI()
    register_error_handlers(app)

    sensitive_info = "SENSITIVE_DB_PASSWORD_12345"

    @app.get("/error")
    def trigger_error():
        raise Exception(f"Database connection failed: {sensitive_info}")

    # raise_server_exceptions=False allows us to capture the 500 response
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/error")

    assert response.status_code == 500
    data = response.json()

    # After the fix, we assert that the sensitive info is NOT leaked
    assert sensitive_info not in data["detail"]
    assert data["detail"] == "An internal error occurred"
