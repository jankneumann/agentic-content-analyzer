"""Security tests for upload endpoint error leakage.

These tests verify that internal error details are not leaked to clients
through error responses.
"""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.workflow_dependencies import get_upload_service


class TestUploadErrorLeakage:
    """Test that upload endpoints don't leak sensitive error details."""

    def test_upload_error_leakage_mitigated(self, monkeypatch):
        """Test that the upload endpoint does NOT leak internal error details.

        This test expects the fix to be in place.
        """
        sensitive_data = "SECRET_DB_CONNECTION_STRING"
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("APP_SECRET_KEY", "")
        monkeypatch.setenv("ADMIN_API_KEY", "")
        monkeypatch.setenv("WORKER_ENABLED", "false")
        from src.config.settings import get_settings

        get_settings.cache_clear()
        upload = AsyncMock()
        upload.max_size_bytes = 1024
        upload.store.side_effect = RuntimeError(f"Connection failed: {sensitive_data}")
        app.dependency_overrides[get_upload_service] = lambda: upload
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/uploads",
                    files={"file": ("test.txt", b"dummy content", "text/plain")},
                )
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

        assert response.status_code == 500
        assert response.headers["content-type"].startswith("application/problem+json")
        assert sensitive_data not in response.text
        assert response.json()["detail"] == "An internal error occurred"
