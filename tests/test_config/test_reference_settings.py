"""Tests for reference extraction and resolution settings."""

import os

import pytest

from src.config.settings import Settings, get_settings


class TestReferenceSettingsDefaults:
    """Verify default values for reference settings."""

    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Clear relevant env vars and caches before each test."""
        get_settings.cache_clear()

        env_vars = [
            "REFERENCE_EXTRACTION_ENABLED",
            "REFERENCE_AUTO_INGEST_ENABLED",
            "REFERENCE_AUTO_INGEST_MAX_DEPTH",
            "REFERENCE_NEO4J_SYNC_ENABLED",
            "REFERENCE_MIN_CONFIDENCE",
        ]
        original = {k: os.environ.get(k) for k in env_vars}
        for k in env_vars:
            os.environ.pop(k, None)

        yield

        for k, v in original.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

        get_settings.cache_clear()

    def test_reference_extraction_enabled_default(self):
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_extraction_enabled is True

    def test_reference_auto_ingest_enabled_default(self):
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_auto_ingest_enabled is False

    def test_reference_auto_ingest_max_depth_default(self):
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_auto_ingest_max_depth == 1

    def test_reference_neo4j_sync_enabled_default(self):
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_neo4j_sync_enabled is True

    def test_reference_min_confidence_default(self):
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_min_confidence == 0.5


class TestReferenceSettingsOverrides:
    """Verify settings can be overridden via environment variables."""

    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Clear relevant env vars and caches before each test."""
        get_settings.cache_clear()

        env_vars = [
            "REFERENCE_EXTRACTION_ENABLED",
            "REFERENCE_AUTO_INGEST_ENABLED",
            "REFERENCE_AUTO_INGEST_MAX_DEPTH",
            "REFERENCE_NEO4J_SYNC_ENABLED",
            "REFERENCE_MIN_CONFIDENCE",
        ]
        original = {k: os.environ.get(k) for k in env_vars}
        for k in env_vars:
            os.environ.pop(k, None)

        yield

        for k, v in original.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

        get_settings.cache_clear()

    def test_override_reference_extraction_enabled(self, monkeypatch):
        monkeypatch.setenv("REFERENCE_EXTRACTION_ENABLED", "false")
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_extraction_enabled is False

    def test_override_reference_auto_ingest_enabled(self, monkeypatch):
        monkeypatch.setenv("REFERENCE_AUTO_INGEST_ENABLED", "true")
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_auto_ingest_enabled is True

    def test_override_reference_auto_ingest_max_depth(self, monkeypatch):
        monkeypatch.setenv("REFERENCE_AUTO_INGEST_MAX_DEPTH", "3")
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_auto_ingest_max_depth == 3

    def test_override_reference_neo4j_sync_enabled(self, monkeypatch):
        monkeypatch.setenv("REFERENCE_NEO4J_SYNC_ENABLED", "false")
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_neo4j_sync_enabled is False

    def test_override_reference_min_confidence(self, monkeypatch):
        monkeypatch.setenv("REFERENCE_MIN_CONFIDENCE", "0.8")
        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.reference_min_confidence == 0.8
