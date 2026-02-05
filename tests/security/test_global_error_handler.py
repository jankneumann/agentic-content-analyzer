
import os
from unittest.mock import patch

# Set required environment variables before importing application modules
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key"
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["GRAPHITI_URL"] = "http://localhost:8080"
os.environ["GRAPHITI_API_KEY"] = "test-key"

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from src.api.middleware.error_handler import register_error_handlers
import pytest

def test_global_error_handler_leakage():
    """
    Test that the global error handler intentionally leaks sensitive information
    before the fix, and hides it after the fix.
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
