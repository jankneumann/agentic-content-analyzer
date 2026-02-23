from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import Settings

client = TestClient(app)


@patch("src.api.dependencies.get_settings")
def test_digest_routes_protected_in_production(mock_get_settings):
    """
    Verify that digest routes are PROTECTED in production.
    """
    # Create a Settings object that looks like production
    settings = MagicMock(spec=Settings)
    settings.is_development = False
    settings.is_production = True
    settings.admin_api_key = "secret-key"

    mock_get_settings.return_value = settings

    # Access without header
    # This should return 401 if protected
    response = client.get("/api/v1/digests/")
    assert response.status_code in [401, 403], (
        f"Digest routes should be protected, got {response.status_code}"
    )


@patch("src.api.dependencies.get_settings")
def test_content_routes_protected_in_production(mock_get_settings):
    """
    Verify that content routes ARE protected in production.
    """
    settings = MagicMock(spec=Settings)
    settings.is_development = False
    settings.is_production = True
    settings.admin_api_key = "secret-key"

    mock_get_settings.return_value = settings

    # Access without header
    response = client.get("/api/v1/contents")

    # This MUST return 401/403
    assert response.status_code in [401, 403], (
        f"Content routes should be protected, got {response.status_code}"
    )
