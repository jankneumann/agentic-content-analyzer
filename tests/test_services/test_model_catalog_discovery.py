"""Tests for live provider catalog discovery (model-registry-freshness)."""

from unittest.mock import patch

from src.services.model_catalog_discovery import (
    ModelCatalogDiscovery,
    find_candidates,
)


class TestFindCandidates:
    def test_returns_unknown_sorted(self):
        assert find_candidates({"c", "a", "b"}, {"b"}) == ["a", "c"]

    def test_all_known_returns_empty(self):
        assert find_candidates({"a", "b"}, {"a", "b", "c"}) == []


class TestDiscover:
    def test_new_model_discovered(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "k")
        disc = ModelCatalogDiscovery()
        with (
            patch.object(
                disc, "_list_google", return_value=["gemini-2.5-flash", "gemini-3.1-flash-lite"]
            ),
            patch(
                "src.services.model_catalog_discovery.known_provider_model_ids",
                return_value={"gemini-2.5-flash"},
            ),
        ):
            report = disc.discover(providers=["google_ai"])

        ids = [c.model_id for c in report.candidates]
        assert "gemini-3.1-flash-lite" in ids
        assert "gemini-2.5-flash" not in ids  # already known
        assert "google_ai" in report.providers_checked

    def test_degrades_without_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        report = ModelCatalogDiscovery().discover(providers=["google_ai"])
        assert report.candidates == []
        assert "google_ai" in report.providers_failed

    def test_other_providers_still_checked_when_one_lacks_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        disc = ModelCatalogDiscovery()
        with (
            patch.object(disc, "_list_anthropic", return_value=["claude-x-new"]),
            patch(
                "src.services.model_catalog_discovery.known_provider_model_ids",
                return_value=set(),
            ),
        ):
            report = disc.discover(providers=["google_ai", "anthropic"])
        assert "google_ai" in report.providers_failed
        assert "anthropic" in report.providers_checked
        assert any(c.model_id == "claude-x-new" for c in report.candidates)

    def test_known_models_not_reported(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        disc = ModelCatalogDiscovery()
        with (
            patch.object(disc, "_list_openai", return_value=["gpt-x"]),
            patch(
                "src.services.model_catalog_discovery.known_provider_model_ids",
                return_value={"gpt-x"},
            ),
        ):
            report = disc.discover(providers=["openai"])
        assert report.candidates == []

    def test_enumerator_exception_degrades(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        disc = ModelCatalogDiscovery()
        with patch.object(disc, "_list_openai", side_effect=RuntimeError("boom")):
            report = disc.discover(providers=["openai"])
        assert "openai" in report.providers_failed
        assert any("boom" in e for e in report.errors)
