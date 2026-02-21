import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.config.settings import Settings
from unittest.mock import patch, MagicMock, AsyncMock

client = TestClient(app)


@patch("src.api.dependencies.get_settings")
def test_search_routes_protected_in_production(mock_get_settings):
    """
    Verify that search routes are PROTECTED in production.
    """
    # Create a Settings object that looks like production
    settings = MagicMock(spec=Settings)
    settings.is_development = False
    settings.is_production = True
    settings.admin_api_key = "secret-key"

    mock_get_settings.return_value = settings

    # Access without header
    # This should return 401/403 if protected
    response = client.get("/api/v1/search?q=test")
    assert response.status_code in [401, 403], (
        f"Search routes should be protected, got {response.status_code}"
    )


@patch("src.api.dependencies.get_settings")
def test_search_routes_accessible_with_key(mock_get_settings):
    """
    Verify that search routes are accessible with valid key.
    """
    settings = MagicMock(spec=Settings)
    settings.is_development = False
    settings.is_production = True
    settings.admin_api_key = "secret-key"

    mock_get_settings.return_value = settings

    # We need to mock get_db and HybridSearchService too, otherwise it will try to access DB
    with (
        patch("src.api.search_routes.get_db") as mock_get_db,
        patch("src.api.search_routes.HybridSearchService") as mock_service,
    ):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_instance = mock_service.return_value
        # Mock search to return a basic SearchResponse structure as expected by the model
        mock_instance.search = AsyncMock(
            return_value=MagicMock(
                results=[],
                total=0,
                meta=MagicMock(
                    bm25_strategy="mock",
                    embedding_provider="mock",
                    embedding_model="mock",
                    rerank_provider=None,
                    rerank_model=None,
                    query_time_ms=0,
                    backend="mock",
                ),
            )
        )

        response = client.get("/api/v1/search?q=test", headers={"X-Admin-Key": "secret-key"})

        # It might fail with validation error on response model or something,
        # but definitely not 401/403.
        assert response.status_code != 401
        assert response.status_code != 403
