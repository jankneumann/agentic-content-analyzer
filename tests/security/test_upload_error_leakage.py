"""Security tests for upload endpoint error leakage.

These tests verify that internal error details are not leaked to clients
through error responses.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestUploadErrorLeakage:
    """Test that upload endpoints don't leak sensitive error details."""

    @pytest.fixture(autouse=True)
    def mock_graphiti(self, monkeypatch):
        """Mock graphiti_core dependencies that may not be installed."""
        graphiti_modules = [
            "graphiti_core",
            "graphiti_core.cross_encoder",
            "graphiti_core.cross_encoder.openai_reranker_client",
            "graphiti_core.embedder",
            "graphiti_core.embedder.openai",
            "graphiti_core.llm_client",
            "graphiti_core.llm_client.anthropic_client",
            "graphiti_core.nodes",
        ]

        for module in graphiti_modules:
            if module not in sys.modules:
                monkeypatch.setitem(sys.modules, module, MagicMock())

    @pytest.fixture
    def client(self):
        """Create a test client for the app."""
        from fastapi.testclient import TestClient

        from src.api.app import app

        return TestClient(app)

    def test_upload_error_leakage_mitigated(self, client):
        """Test that the upload endpoint does NOT leak internal error details.

        This test expects the fix to be in place.
        """
        sensitive_data = "SECRET_DB_CONNECTION_STRING"

        with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.ingest_bytes = AsyncMock(
                side_effect=RuntimeError(f"Connection failed: {sensitive_data}")
            )

            with patch("src.api.upload_routes.get_db"):
                files = {"file": ("test.txt", b"dummy content", "text/plain")}
                response = client.post("/api/v1/documents/upload", files=files)

                assert response.status_code == 500

                detail = response.json()["detail"]
                assert sensitive_data not in detail
                # Error message should be generic without sensitive details
                assert "internal error" in detail.lower()
