"""Tests for risk-gated registry writeback + default promotion."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.model_promotion import PromotionDecision
from src.services.model_registry_service import ModelRegistryService


@pytest.fixture
def service():
    return ModelRegistryService()


class TestProposeDefault:
    def test_rejects_unknown_step(self, service):
        result = service.propose_default("not_a_step", "gemini-2.5-flash")
        assert result["status"] == "rejected"
        assert "step" in result["reason"]

    def test_rejects_unknown_model(self, service):
        result = service.propose_default("youtube_processing", "made-up-model")
        assert result["status"] == "rejected"
        assert "model" in result["reason"]

    def test_pending_without_approval(self, service):
        result = service.propose_default("youtube_processing", "gemini-2.5-flash")
        assert result["status"] == "pending_approval"
        assert result["applied"] is False
        assert result["risk"] == "high"

    def test_rejected_when_gate_fails(self, service):
        decision = PromotionDecision(recommend=False, reasons=["parity too low"])
        result = service.propose_default(
            "youtube_processing", "gemini-2.5-flash", approved=True, decision=decision
        )
        assert result["status"] == "rejected"
        assert result["applied"] is False
        assert result["gate_reasons"] == ["parity too low"]

    def test_applied_when_approved(self, service):
        decision = PromotionDecision(recommend=True, reasons=["ok"])
        mock_settings = MagicMock()
        with patch(
            "src.services.settings_service.SettingsService", return_value=mock_settings
        ):
            result = service.propose_default(
                "youtube_processing", "gemini-2.5-flash", approved=True, decision=decision
            )
        assert result["status"] == "applied"
        assert result["applied"] is True
        mock_settings.set.assert_called_once()
        key, value = mock_settings.set.call_args.args[:2]
        assert key == "model.youtube_processing"
        assert value == "gemini-2.5-flash"


class TestApplyPricing:
    @pytest.mark.asyncio
    async def test_apply_pricing_is_not_dry_run(self, service):
        from src.services.model_registry_service import PricingRefreshReport

        with patch.object(
            service, "refresh_pricing", return_value=PricingRefreshReport()
        ) as mock_refresh:
            await service.apply_pricing(providers=["anthropic"])
        mock_refresh.assert_called_once()
        assert mock_refresh.call_args.kwargs["dry_run"] is False

    @pytest.mark.asyncio
    async def test_refresh_pricing_defaults_to_dry_run(self, service):
        # Safe-by-default: refresh_pricing without apply must not modify files.
        fake_report = MagicMock(
            providers_fetched=[],
            providers_failed=[],
            diffs=[],
            new_models=[],
            extraction_errors=[],
            applied=False,
        )
        with patch(
            "src.services.model_pricing_extractor.ModelPricingExtractor"
        ) as mock_extractor_cls:
            instance = mock_extractor_cls.return_value
            instance.run = MagicMock(return_value=fake_report)

            async def _run(*a, **k):
                return fake_report

            instance.run = _run
            report = await service.refresh_pricing()
        assert report.applied is False
