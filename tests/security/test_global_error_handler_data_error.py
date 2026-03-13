"""Security tests for global error handler's DataError handling."""

import pytest
from asyncpg.exceptions import DataError as AsyncpgDataError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DataError

from src.api.middleware.error_handler import register_error_handlers


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up required environment variables for tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GRAPHITI_URL", "http://localhost:8080")
    monkeypatch.setenv("GRAPHITI_API_KEY", "test-key")


def test_data_error_handler_leakage():
    """Test that the DataError handler does not leak database details."""
    app = FastAPI()
    register_error_handlers(app)

    sensitive_info = "SENSITIVE_DB_DETAIL_123"

    @app.get("/data-error")
    def trigger_data_error():
        raise DataError("STATEMENT", "PARAMS", sensitive_info)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/data-error")

    assert response.status_code == 422
    data = response.json()

    assert sensitive_info not in data["detail"]
    assert data["detail"] == "Invalid parameter format or value"


def test_asyncpg_data_error_handler_leakage():
    """Test that the AsyncpgDataError handler does not leak database details."""
    app = FastAPI()
    register_error_handlers(app)

    sensitive_info = "SENSITIVE_ASYNCPG_DETAIL_456"

    @app.get("/asyncpg-error")
    def trigger_asyncpg_error():
        raise AsyncpgDataError(sensitive_info)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/asyncpg-error")

    assert response.status_code == 422
    data = response.json()

    assert sensitive_info not in data["detail"]
    assert data["detail"] == "Invalid parameter format or value"
