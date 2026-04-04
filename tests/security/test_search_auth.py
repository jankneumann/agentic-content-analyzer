from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import Settings
from src.models.search import SearchMeta, SearchResponse

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
    settings.app_secret_key = "app-secret-key"

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
    settings.app_secret_key = "app-secret-key"

    mock_get_settings.return_value = settings

    # We need to mock get_db and HybridSearchService too, otherwise it will try to access DB
    with (
        patch("src.api.search_routes.get_db") as mock_get_db,
        patch("src.api.search_routes.HybridSearchService") as mock_service,
    ):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_instance = mock_service.return_value
        mock_instance.search = AsyncMock(
            return_value=SearchResponse(
                results=[],
                total=0,
                meta=SearchMeta(
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

        assert response.status_code == 200
