"""GEMINI_API_KEY is the Gemini key name; GOOGLE_API_KEY is its deprecated alias."""

from __future__ import annotations

import pytest

from src.config.models import Provider
from src.config.settings import Settings, get_gemini_api_key_from_env


@pytest.fixture
def no_gemini_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return monkeypatch


def test_env_prefers_gemini_api_key(no_gemini_env: pytest.MonkeyPatch) -> None:
    no_gemini_env.setenv("GEMINI_API_KEY", "gemini")
    no_gemini_env.setenv("GOOGLE_API_KEY", "legacy")

    assert get_gemini_api_key_from_env() == "gemini"


def test_env_falls_back_to_legacy_google_api_key(no_gemini_env: pytest.MonkeyPatch) -> None:
    no_gemini_env.setenv("GOOGLE_API_KEY", "legacy")

    assert get_gemini_api_key_from_env() == "legacy"


def test_env_ignores_empty_gemini_api_key(no_gemini_env: pytest.MonkeyPatch) -> None:
    # GitHub Actions injects unset secrets as empty strings.
    no_gemini_env.setenv("GEMINI_API_KEY", "")
    no_gemini_env.setenv("GOOGLE_API_KEY", "legacy")

    assert get_gemini_api_key_from_env() == "legacy"


def test_env_returns_none_when_unset(no_gemini_env: pytest.MonkeyPatch) -> None:
    assert get_gemini_api_key_from_env() is None


def test_settings_maps_legacy_google_api_key_onto_gemini() -> None:
    settings = Settings(_env_file=None, gemini_api_key=None, google_api_key="legacy")

    assert settings.gemini_api_key == "legacy"


def test_settings_keeps_explicit_gemini_api_key() -> None:
    settings = Settings(_env_file=None, gemini_api_key="gemini", google_api_key="legacy")

    assert settings.gemini_api_key == "gemini"
    # The legacy key stays the YouTube fallback; the restricted Gemini key never is.
    assert settings.get_youtube_api_key() == "legacy"


def test_youtube_does_not_fall_back_to_gemini_key() -> None:
    settings = Settings(
        _env_file=None, gemini_api_key="gemini", google_api_key=None, youtube_api_key=None
    )

    assert settings.get_youtube_api_key() is None


def test_google_ai_provider_uses_gemini_api_key() -> None:
    settings = Settings(_env_file=None, gemini_api_key="gemini", google_api_key=None)

    providers = settings.get_model_config().get_providers_for_model("gemini-2.5-flash")

    google_ai = [p for p in providers if p.provider is Provider.GOOGLE_AI]
    assert [p.api_key for p in google_ai] == ["gemini"]
