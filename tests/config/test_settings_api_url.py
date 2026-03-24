"""Tests for api_base_url and api_timeout Settings fields."""

from unittest.mock import patch

from src.config.settings import Settings, get_settings


def test_defaults():
    """api_base_url and api_timeout have sensible defaults."""
    s = Settings(_env_file=None, anthropic_api_key="test-key")
    assert s.api_base_url == "http://localhost:8000"
    assert s.api_timeout == 300


def test_env_override(monkeypatch):
    """Environment variables override default api_base_url and api_timeout."""
    monkeypatch.setenv("API_BASE_URL", "https://my-api.com")
    monkeypatch.setenv("API_TIMEOUT", "60")
    s = Settings(_env_file=None, anthropic_api_key="test-key")
    assert s.api_base_url == "https://my-api.com"
    assert s.api_timeout == 60


def test_get_api_client_uses_settings(monkeypatch):
    """get_api_client() passes api_base_url and api_timeout to ApiClient."""
    monkeypatch.setenv("API_BASE_URL", "https://staging.example.com")
    monkeypatch.setenv("API_TIMEOUT", "120")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

    # Clear cached settings so monkeypatched env vars take effect
    get_settings.cache_clear()
    try:
        with patch("src.cli.api_client.ApiClient") as MockApiClient:
            from src.cli.api_client import get_api_client

            get_api_client()

            MockApiClient.assert_called_once_with(
                base_url="https://staging.example.com",
                admin_key="test-admin-key",
                timeout=120.0,
            )
    finally:
        get_settings.cache_clear()
