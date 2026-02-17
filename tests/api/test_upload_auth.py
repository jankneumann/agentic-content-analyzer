from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import get_settings


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure we are in production mode for strict auth testing."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_upload_dependencies():
    """Setup common mocks for upload endpoint testing."""
    with (
        patch("src.api.upload_routes.get_db") as mock_get_db,
        patch("src.api.upload_routes.FileContentIngestionService") as mock_service,
        patch("src.api.upload_routes.get_parser_router") as mock_get_router,
    ):
        # Mock DB
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock Ingestion Service
        mock_content = MagicMock(
            id=1,
            status=MagicMock(value="parsed"),
            title="Test",
            canonical_id=None,
            metadata_json={},
            markdown_content="Test",
            parser_used="markitdown",
        )
        mock_instance = mock_service.return_value
        mock_instance.ingest_bytes = AsyncMock(return_value=mock_content)

        # Mock Router
        mock_router = MagicMock()
        mock_router.available_parsers = ["markitdown"]

        # Setup specific parser mocks for validity checks
        mock_parser = MagicMock()
        mock_parser.supported_formats = ["txt"]
        mock_parser.fallback_formats = []
        mock_router.parsers = {"markitdown": mock_parser}
        mock_router.route.return_value.name = "markitdown"

        mock_get_router.return_value = mock_router

        yield {"db": mock_db, "service": mock_instance, "router": mock_router}


def test_upload_missing_auth_rejected(clean_env, mock_upload_dependencies):
    """
    Verify that upload endpoint rejects requests without authentication in production.
    """
    client = TestClient(app)

    # 1. Upload without X-Admin-Key -> Should be 401
    files = {"file": ("test.txt", b"content", "text/plain")}
    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 401


def test_upload_invalid_auth_rejected(clean_env, mock_upload_dependencies):
    """
    Verify that upload endpoint rejects requests with invalid authentication.
    """
    client = TestClient(app)

    files = {"file": ("test.txt", b"content", "text/plain")}
    response = client.post(
        "/api/v1/documents/upload", files=files, headers={"X-Admin-Key": "wrong-key"}
    )

    assert response.status_code == 403


def test_upload_valid_auth_accepted(clean_env, mock_upload_dependencies):
    """
    Verify that upload endpoint accepts requests with valid authentication.
    """
    client = TestClient(app)

    files = {"file": ("test.txt", b"content", "text/plain")}
    # Valid key
    response = client.post(
        "/api/v1/documents/upload", files=files, headers={"X-Admin-Key": "secret-key"}
    )

    if response.status_code != 200:
        print(f"Error: {response.text}")

    assert response.status_code == 200
