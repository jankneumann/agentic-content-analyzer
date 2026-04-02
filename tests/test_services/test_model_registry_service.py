"""Tests for ModelRegistryService.

Verifies model listing, detail retrieval, pricing refresh delegation,
and Pydantic response model serialization.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.model_registry_service import (
    ModelDetail,
    ModelRegistryService,
    ModelSummary,
    PricingRefreshReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    return ModelRegistryService()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    def test_returns_all_models(self, service):
        """Should return at least 10 models from the registry."""
        models = service.list_models()
        assert len(models) >= 10
        assert all(isinstance(m, ModelSummary) for m in models)

    def test_each_model_has_required_fields(self, service):
        """Each model should have id, name, family, and providers."""
        models = service.list_models()
        for m in models:
            assert m.id
            assert m.name
            assert m.family
            assert isinstance(m.providers, list)

    def test_filter_by_family_claude(self, service):
        """Filtering by 'claude' should return only Claude models."""
        models = service.list_models(family="claude")
        assert len(models) >= 3
        assert all(m.family == "claude" for m in models)

    def test_filter_by_family_gemini(self, service):
        """Filtering by 'gemini' should return only Gemini models."""
        models = service.list_models(family="gemini")
        assert len(models) >= 3
        assert all(m.family == "gemini" for m in models)

    def test_filter_by_nonexistent_family_returns_empty(self, service):
        """Filtering by unknown family should return empty list."""
        models = service.list_models(family="nonexistent")
        assert models == []

    def test_models_include_cost_data(self, service):
        """Most models should have cost data from their primary provider."""
        models = service.list_models()
        models_with_cost = [m for m in models if m.cost_per_mtok_input is not None]
        assert len(models_with_cost) >= 8

    def test_serializes_to_dict(self, service):
        """ModelSummary should serialize to a dict with all fields."""
        models = service.list_models()
        d = models[0].model_dump()
        assert "id" in d
        assert "name" in d
        assert "family" in d
        assert "providers" in d
        assert "cost_per_mtok_input" in d


# ---------------------------------------------------------------------------
# get_model
# ---------------------------------------------------------------------------


class TestGetModel:
    def test_returns_model_detail(self, service):
        """Should return ModelDetail with provider pricing."""
        detail = service.get_model("claude-haiku-4-5")
        assert detail is not None
        assert isinstance(detail, ModelDetail)
        assert detail.id == "claude-haiku-4-5"
        assert detail.family == "claude"
        assert detail.name == "Claude 4.5 Haiku"

    def test_includes_provider_pricing(self, service):
        """Claude Haiku should have pricing from multiple providers."""
        detail = service.get_model("claude-haiku-4-5")
        assert detail is not None
        assert len(detail.provider_pricing) >= 2
        providers = [p.provider for p in detail.provider_pricing]
        assert "anthropic" in providers

    def test_pricing_has_all_fields(self, service):
        """Each provider pricing entry should have complete data."""
        detail = service.get_model("claude-haiku-4-5")
        assert detail is not None
        for p in detail.provider_pricing:
            assert p.provider
            assert p.provider_model_id
            assert p.cost_per_mtok_input >= 0
            assert p.cost_per_mtok_output >= 0
            assert p.context_window > 0
            assert p.max_output_tokens >= 0
            assert p.tier

    def test_returns_none_for_unknown_model(self, service):
        """Should return None for a model ID that doesn't exist."""
        result = service.get_model("nonexistent-model-999")
        assert result is None

    def test_pricing_sorted_by_provider(self, service):
        """Provider pricing should be sorted alphabetically."""
        detail = service.get_model("claude-haiku-4-5")
        assert detail is not None
        providers = [p.provider for p in detail.provider_pricing]
        assert providers == sorted(providers)

    def test_serializes_to_dict(self, service):
        """ModelDetail should serialize to a complete dict."""
        detail = service.get_model("claude-haiku-4-5")
        assert detail is not None
        d = detail.model_dump()
        assert "provider_pricing" in d
        assert len(d["provider_pricing"]) >= 2


# ---------------------------------------------------------------------------
# refresh_pricing
# ---------------------------------------------------------------------------


class TestRefreshPricing:
    @pytest.mark.asyncio
    async def test_delegates_to_extractor(self, service):
        """Should call ModelPricingExtractor.run() with correct args."""
        mock_report = MagicMock()
        mock_report.providers_fetched = ["anthropic"]
        mock_report.providers_failed = []
        mock_report.diffs = []
        mock_report.new_models = []
        mock_report.extraction_errors = []
        mock_report.applied = False

        with patch(
            "src.services.model_registry_service.ModelPricingExtractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            instance.run = AsyncMock(return_value=mock_report)

            result = await service.refresh_pricing(
                providers=["anthropic"], dry_run=True
            )

            instance.run.assert_called_once_with(
                providers=["anthropic"], dry_run=True
            )
            assert isinstance(result, PricingRefreshReport)
            assert result.providers_fetched == ["anthropic"]
            assert result.timestamp is not None

    @pytest.mark.asyncio
    async def test_stores_last_refresh(self, service):
        """Should store the refresh report for later retrieval."""
        mock_report = MagicMock()
        mock_report.providers_fetched = ["openai"]
        mock_report.providers_failed = []
        mock_report.diffs = []
        mock_report.new_models = []
        mock_report.extraction_errors = []
        mock_report.applied = False

        with patch(
            "src.services.model_registry_service.ModelPricingExtractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            instance.run = AsyncMock(return_value=mock_report)

            await service.refresh_pricing(providers=["openai"], dry_run=True)
            last = service.get_last_refresh()
            assert last is not None
            assert last.providers_fetched == ["openai"]


# ---------------------------------------------------------------------------
# get_last_refresh
# ---------------------------------------------------------------------------


class TestGetLastRefresh:
    def test_returns_none_initially(self):
        """Should return None if no refresh has been run."""
        # Reset module state
        import src.services.model_registry_service as mod

        original = mod._last_refresh_report
        mod._last_refresh_report = None
        try:
            service = ModelRegistryService()
            assert service.get_last_refresh() is None
        finally:
            mod._last_refresh_report = original


# ---------------------------------------------------------------------------
# PricingRefreshReport
# ---------------------------------------------------------------------------


class TestPricingRefreshReport:
    def test_has_changes_with_diffs(self):
        from src.services.model_registry_service import PricingDiffItem

        report = PricingRefreshReport(
            diffs=[PricingDiffItem(provider_key="a.b", field="cost", current_value=1.0, extracted_value=2.0)]
        )
        assert report.has_changes is True

    def test_has_changes_with_new_models(self):
        from src.services.model_registry_service import NewModelItem

        report = PricingRefreshReport(
            new_models=[NewModelItem(model_id="x", provider_model_id="x-v1", cost_per_mtok_input=1.0, cost_per_mtok_output=2.0)]
        )
        assert report.has_changes is True

    def test_no_changes_when_empty(self):
        report = PricingRefreshReport()
        assert report.has_changes is False
