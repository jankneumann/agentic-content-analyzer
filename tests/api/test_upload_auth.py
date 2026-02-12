import pytest
from fastapi.testclient import TestClient

def test_unauthenticated_upload_vulnerability(client, monkeypatch):
    """
    Test that the upload endpoint is secure (requires auth)
    when configured in a production-like environment.
    """
    # Force production environment
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")

    # Reload settings to apply env vars
    from src.config.settings import get_settings
    get_settings.cache_clear()

    # Use the raw client to avoid automatic header injection
    # client fixture returns AuthenticatedTestClient, ._client is the raw TestClient
    raw_client = client._client

    # Create a small test file
    files = {"file": ("test.txt", b"test content", "text/plain")}

    # Attempt upload without X-Admin-Key header
    response = raw_client.post("/api/v1/documents/upload", files=files)

    # Assert that it IS SECURE (returns 401)
    # This assertion will FAIL if the endpoint is vulnerable (returns 200)
    assert response.status_code == 401, f"Endpoint is vulnerable! Expected 401, got {response.status_code}"
