"""Tests for model registry API routes.

Verifies listing models, getting model details, pricing endpoints,
and pricing refresh — all using the authenticated test client.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# GET /api/v1/models/
# ---------------------------------------------------------------------------


class TestListModels:
    def test_list_all_models(self, client):
        """Should return all models from the registry."""
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "count" in data
        assert data["count"] >= 10
        assert len(data["models"]) == data["count"]

    def test_list_models_has_required_fields(self, client):
        """Each model in the list should have id, name, family."""
        resp = client.get("/api/v1/models")
        data = resp.json()
        for m in data["models"]:
            assert "id" in m
            assert "name" in m
            assert "family" in m
            assert "providers" in m

    def test_filter_by_family(self, client):
        """Should filter models by family query param."""
        resp = client.get("/api/v1/models?family=claude")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 3
        for m in data["models"]:
            assert m["family"] == "claude"

    def test_filter_unknown_family_returns_empty(self, client):
        """Filtering by nonexistent family should return empty list."""
        resp = client.get("/api/v1/models?family=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["models"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}
# ---------------------------------------------------------------------------


class TestGetModel:
    def test_get_existing_model(self, client):
        """Should return model detail with provider pricing."""
        resp = client.get("/api/v1/models/claude-haiku-4-5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "claude-haiku-4-5"
        assert data["family"] == "claude"
        assert "provider_pricing" in data
        assert len(data["provider_pricing"]) >= 2

    def test_get_nonexistent_model(self, client):
        """Should return 404 for unknown model."""
        resp = client.get("/api/v1/models/nonexistent-model")
        assert resp.status_code == 404

    def test_provider_pricing_has_all_fields(self, client):
        """Each provider pricing entry should have complete data."""
        resp = client.get("/api/v1/models/claude-haiku-4-5")
        data = resp.json()
        for p in data["provider_pricing"]:
            assert "provider" in p
            assert "provider_model_id" in p
            assert "cost_per_mtok_input" in p
            assert "cost_per_mtok_output" in p
            assert "context_window" in p
            assert "max_output_tokens" in p
            assert "tier" in p


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}/pricing
# ---------------------------------------------------------------------------


class TestGetModelPricing:
    def test_get_pricing(self, client):
        """Should return pricing breakdown for a model."""
        resp = client.get("/api/v1/models/claude-haiku-4-5/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == "claude-haiku-4-5"
        assert "providers" in data
        assert len(data["providers"]) >= 2

    def test_pricing_404(self, client):
        """Should return 404 for unknown model pricing."""
        resp = client.get("/api/v1/models/nonexistent/pricing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/models/pricing/refresh
# ---------------------------------------------------------------------------


class TestRefreshPricing:
    def test_refresh_dry_run(self, client):
        """Should trigger pricing refresh in dry_run mode."""
        mock_report = AsyncMock()
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

            resp = client.post(
                "/api/v1/models/pricing/refresh",
                json={"providers": ["anthropic"], "dry_run": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["providers_fetched"] == ["anthropic"]
            assert data["applied"] is False


# ---------------------------------------------------------------------------
# GET /api/v1/models/pricing/status
# ---------------------------------------------------------------------------


class TestPricingStatus:
    def test_status_no_refresh_yet(self, client):
        """Should indicate no refresh has been run."""
        # Reset module state to ensure clean test
        import src.services.model_registry_service as mod

        original = mod._last_refresh_report
        mod._last_refresh_report = None
        try:
            resp = client.get("/api/v1/models/pricing/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data
        finally:
            mod._last_refresh_report = original
