import sys
from unittest.mock import MagicMock

# Mock graphiti_core and other potential missing dependencies before any imports
# This allows running this test in an environment where graphiti_core is missing
mock_graphiti = MagicMock()
sys.modules["graphiti_core"] = mock_graphiti
sys.modules["graphiti_core.cross_encoder"] = MagicMock()
sys.modules["graphiti_core.cross_encoder.openai_reranker_client"] = MagicMock()
sys.modules["graphiti_core.embedder"] = MagicMock()
sys.modules["graphiti_core.embedder.openai"] = MagicMock()
sys.modules["graphiti_core.llm_client"] = MagicMock()
sys.modules["graphiti_core.llm_client.anthropic_client"] = MagicMock()
sys.modules["graphiti_core.nodes"] = MagicMock()

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402

client = TestClient(app)


def test_upload_error_leakage_mitigated():
    """
    Test that the upload endpoint NO LONGER leaks internal error details.
    This test expects the fix to be in place.
    """
    sensitive_data = "SECRET_DB_CONNECTION_STRING"

    # Mock the service to raise an exception containing sensitive data
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
        mock_instance = mock_service.return_value
        # Mocking ingest_bytes to raise an exception
        mock_instance.ingest_bytes = AsyncMock(
            side_effect=RuntimeError(f"Connection failed: {sensitive_data}")
        )

        # We also need to mock get_db to avoid actual DB connection
        with patch("src.api.upload_routes.get_db"):
            files = {"file": ("test.txt", b"dummy content", "text/plain")}

            response = client.post("/api/v1/documents/upload", files=files)

            assert response.status_code == 500

            # Verify that sensitive data is NOT leaked in the response
            detail = response.json()["detail"]
            assert sensitive_data not in detail

            # Verify that we get the generic error message
            assert "An internal error occurred during processing" in detail
