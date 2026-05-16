from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import Settings

client = TestClient(app)


def _make_production_settings_mock() -> MagicMock:
    """Build a Settings mock with all attributes the auth layers touch.

    `verify_admin_key` (dependencies.py:93) reads `settings.app_secret_key`
    even when only checking for an admin key, so missing it raises
    AttributeError → 500. AuthMiddleware also reads `app_secret_key` for
    JWT cookie validation.
    """
    settings = MagicMock(spec=Settings)
    settings.is_development = False
    settings.is_production = True
    settings.admin_api_key = "secret-key"
    settings.app_secret_key = "app-secret-key"
    return settings


@patch("src.api.middleware.auth.get_settings")
@patch("src.api.dependencies.get_settings")
def test_digest_routes_protected_in_production(mock_deps_settings, mock_middleware_settings):
    """
    Verify that digest routes are PROTECTED in production.
    """
    settings = _make_production_settings_mock()
    mock_deps_settings.return_value = settings
    mock_middleware_settings.return_value = settings

    # Access without header
    # This should return 401 if protected
    response = client.get("/api/v1/digests/")
    assert response.status_code in [401, 403], (
        f"Digest routes should be protected, got {response.status_code}"
    )


@patch("src.api.middleware.auth.get_settings")
@patch("src.api.dependencies.get_settings")
def test_content_routes_protected_in_production(mock_deps_settings, mock_middleware_settings):
    """
    Verify that content routes ARE protected in production.
    """
    settings = _make_production_settings_mock()
    mock_deps_settings.return_value = settings
    mock_middleware_settings.return_value = settings

    # Access without header
    response = client.get("/api/v1/contents")

    # This MUST return 401/403
    assert response.status_code in [401, 403], (
        f"Content routes should be protected, got {response.status_code}"
    )
