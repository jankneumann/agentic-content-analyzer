"""Unit tests for InfrastructurePricingService.

Tests cover Neon cost estimation, Resend cost estimation, combined predictions,
and plan comparison helpers. The service loads settings/pricing.yaml directly,
so no mocking is needed for pricing data.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from src.services.infrastructure_pricing_service import (
    CostPrediction,
    InfrastructurePricingService,
    NeonCostBreakdown,
    PlanComparison,
    ResendCostBreakdown,
)


@pytest.fixture
def service() -> InfrastructurePricingService:
    return InfrastructurePricingService()


# ---------------------------------------------------------------------------
# Neon Cost Estimation
# ---------------------------------------------------------------------------


class TestNeonEstimation:
    """Tests for estimate_neon_cost."""

    def test_free_tier_returns_zero_total(self, service: InfrastructurePricingService):
        """Free tier: total is always 0.0 regardless of requested usage."""
        result = service.estimate_neon_cost(
            plan="free",
            compute_hours_per_day=10,
            storage_gb=20,
        )
        assert isinstance(result, NeonCostBreakdown)
        assert result.plan == "free"
        assert result.total == 0.0
        assert result.base_price == 0.0
        assert result.compute_cost == 0.0
        assert result.storage_cost == 0.0

    def test_free_tier_caps_compute_at_included_hours(self, service: InfrastructurePricingService):
        """Free tier caps reported compute hours at the included limit (100h)."""
        result = service.estimate_neon_cost(
            plan="free",
            compute_hours_per_day=10,  # 10 * 30 = 300, exceeds 100
        )
        assert result.compute_hours_per_month == 100  # capped at included

    def test_free_tier_caps_storage_at_max(self, service: InfrastructurePricingService):
        """Free tier caps reported storage at max_storage_gb (5 GB)."""
        result = service.estimate_neon_cost(
            plan="free",
            storage_gb=20,
        )
        assert result.storage_gb == 5  # capped at max_storage_gb

    def test_free_tier_pitr_and_snapshot_zero(self, service: InfrastructurePricingService):
        """Free tier always reports 0 for PITR and snapshot storage."""
        result = service.estimate_neon_cost(plan="free", pitr_gb=10, snapshot_gb=10)
        assert result.pitr_gb == 0.0
        assert result.snapshot_gb == 0.0
        assert result.pitr_cost == 0.0
        assert result.snapshot_cost == 0.0

    def test_launch_plan_compute_cost(self, service: InfrastructurePricingService):
        """Launch plan: compute_cost = (hours_per_day * 30) * cost_per_compute_hour."""
        hours_per_day = 3
        result = service.estimate_neon_cost(
            plan="launch",
            compute_hours_per_day=hours_per_day,
            storage_gb=0,
            pitr_gb=0,
            snapshot_gb=0,
        )
        expected_compute = (hours_per_day * 30) * 0.14  # 90 * 0.14 = 12.60
        assert result.compute_cost == round(expected_compute, 4)
        assert result.compute_hours_per_month == hours_per_day * 30

    def test_launch_plan_storage_cost(self, service: InfrastructurePricingService):
        """Launch plan: storage_cost = gb * cost_per_storage_gb for <= 50 GB."""
        storage = 10
        result = service.estimate_neon_cost(
            plan="launch",
            compute_hours_per_day=0,
            storage_gb=storage,
            pitr_gb=0,
            snapshot_gb=0,
        )
        expected_storage = storage * 0.30  # 10 * 0.30 = 3.00
        assert result.storage_cost == round(expected_storage, 4)

    def test_launch_plan_tiered_storage_above_50gb(self, service: InfrastructurePricingService):
        """Tiered storage: 50 * rate1 + (excess) * rate2 when above 50 GB."""
        storage = 80
        result = service.estimate_neon_cost(
            plan="launch",
            compute_hours_per_day=0,
            storage_gb=storage,
            pitr_gb=0,
            snapshot_gb=0,
        )
        expected_storage = 50 * 0.30 + (80 - 50) * 0.15  # 15.00 + 4.50 = 19.50
        assert result.storage_cost == round(expected_storage, 4)

    def test_launch_plan_minimum_spend(self, service: InfrastructurePricingService):
        """When usage < monthly_price, total equals monthly_price (minimum spend)."""
        # Very low usage: 0.1 hours/day, 0.1 GB storage, 0 PITR/snapshot
        result = service.estimate_neon_cost(
            plan="launch",
            compute_hours_per_day=0.1,
            storage_gb=0.1,
            pitr_gb=0,
            snapshot_gb=0,
        )
        usage = (0.1 * 30) * 0.14 + 0.1 * 0.30  # 0.42 + 0.03 = 0.45
        assert usage < 5.00, "Sanity: usage should be below minimum spend"
        assert result.total == 5.00  # minimum spend

    def test_launch_plan_pitr_and_snapshot_costs(self, service: InfrastructurePricingService):
        """PITR and snapshot costs are calculated correctly."""
        result = service.estimate_neon_cost(
            plan="launch",
            compute_hours_per_day=0,
            storage_gb=0,
            pitr_gb=10,
            snapshot_gb=20,
        )
        expected_pitr = 10 * 0.20  # 2.00
        expected_snapshot = 20 * 0.09  # 1.80
        assert result.pitr_cost == round(expected_pitr, 4)
        assert result.snapshot_cost == round(expected_snapshot, 4)

    def test_default_parameters_from_yaml(self, service: InfrastructurePricingService):
        """Default parameters come from the YAML defaults section."""
        result = service.estimate_neon_cost()
        # Defaults: plan=launch, hours=2/day, storage=5, pitr=2, snapshot=0
        assert result.plan == "launch"
        assert result.compute_hours_per_month == 2 * 30  # 60
        assert result.storage_gb == 5
        assert result.pitr_gb == 2
        assert result.snapshot_gb == 0

        # Verify calculated values
        expected_compute = 60 * 0.14  # 8.40
        expected_storage = 5 * 0.30  # 1.50
        expected_pitr = 2 * 0.20  # 0.40
        expected_total = max(expected_compute + expected_storage + expected_pitr, 5.00)
        assert result.compute_cost == round(expected_compute, 4)
        assert result.storage_cost == round(expected_storage, 4)
        assert result.total == round(expected_total, 2)

    def test_unknown_plan_raises_value_error(self, service: InfrastructurePricingService):
        """Unknown plan name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown Neon plan"):
            service.estimate_neon_cost(plan="nonexistent")

    def test_scale_plan_same_rates_as_launch(self, service: InfrastructurePricingService):
        """Scale plan has same per-unit rates as Launch but higher compute ceiling."""
        launch = service.estimate_neon_cost(
            plan="launch", compute_hours_per_day=2, storage_gb=10, pitr_gb=1, snapshot_gb=1,
        )
        scale = service.estimate_neon_cost(
            plan="scale", compute_hours_per_day=2, storage_gb=10, pitr_gb=1, snapshot_gb=1,
        )
        assert launch.compute_cost == scale.compute_cost
        assert launch.storage_cost == scale.storage_cost
        assert launch.total == scale.total


# ---------------------------------------------------------------------------
# Resend Cost Estimation
# ---------------------------------------------------------------------------


class TestResendEstimation:
    """Tests for estimate_resend_cost."""

    def test_free_tier_within_limits(self, service: InfrastructurePricingService):
        """Free tier within limits: total=0.0, overage=0."""
        result = service.estimate_resend_cost(plan="free", emails_per_month=500)
        assert isinstance(result, ResendCostBreakdown)
        assert result.plan == "free"
        assert result.total == 0.0
        assert result.base_price == 0.0
        assert result.overage_cost == 0.0
        assert result.overage_emails == 0
        assert result.included_emails == 3000

    def test_free_tier_no_pay_as_you_go(self, service: InfrastructurePricingService):
        """Free tier has no pay-as-you-go: overage_cost stays 0 even when exceeding."""
        result = service.estimate_resend_cost(plan="free", emails_per_month=5000)
        assert result.overage_emails == 2000  # 5000 - 3000
        assert result.overage_cost == 0.0  # no pay_as_you_go on free
        assert result.total == 0.0

    def test_pro_plan_no_overage(self, service: InfrastructurePricingService):
        """Pro plan within included emails: only base price."""
        result = service.estimate_resend_cost(plan="pro", emails_per_month=10000)
        assert result.base_price == 20.00
        assert result.overage_cost == 0.0
        assert result.total == 20.00
        assert result.overage_emails == 0

    def test_pro_plan_overage(self, service: InfrastructurePricingService):
        """Pro plan overage: ceil(overage/1000) * overage_rate."""
        emails = 53500  # 3500 over the 50000 limit
        result = service.estimate_resend_cost(plan="pro", emails_per_month=emails)
        overage = emails - 50000  # 3500
        buckets = math.ceil(overage / 1000)  # ceil(3.5) = 4
        expected_overage = buckets * 0.44  # 4 * 0.44 = 1.76
        assert result.overage_emails == overage
        assert result.overage_cost == round(expected_overage, 2)
        assert result.total == round(20.00 + expected_overage, 2)

    def test_overage_billed_in_1000_email_buckets(self, service: InfrastructurePricingService):
        """1 email over = 1 full bucket charged."""
        # Exactly 1 email over the 50000 limit
        result = service.estimate_resend_cost(plan="pro", emails_per_month=50001)
        assert result.overage_emails == 1
        # 1 email still costs 1 bucket
        expected_overage = 1 * 0.44  # 1 bucket * 0.44
        assert result.overage_cost == round(expected_overage, 2)

    def test_pro_plan_exact_boundary(self, service: InfrastructurePricingService):
        """Exactly at included limit: no overage."""
        result = service.estimate_resend_cost(plan="pro", emails_per_month=50000)
        assert result.overage_emails == 0
        assert result.overage_cost == 0.0
        assert result.total == 20.00

    def test_scale_plan_overage(self, service: InfrastructurePricingService):
        """Scale plan uses its own overage rate."""
        emails = 102000  # 2000 over the 100000 limit
        result = service.estimate_resend_cost(plan="scale", emails_per_month=emails)
        buckets = math.ceil(2000 / 1000)  # 2
        expected_overage = buckets * 0.90  # 2 * 0.90 = 1.80
        assert result.overage_cost == round(expected_overage, 2)
        assert result.total == round(90.00 + expected_overage, 2)

    def test_default_parameters_from_yaml(self, service: InfrastructurePricingService):
        """Defaults come from YAML: plan=free, emails_per_month=500."""
        result = service.estimate_resend_cost()
        assert result.plan == "free"
        assert result.emails_per_month == 500
        assert result.total == 0.0

    def test_unknown_plan_raises_value_error(self, service: InfrastructurePricingService):
        """Unknown plan name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown Resend plan"):
            service.estimate_resend_cost(plan="nonexistent")


# ---------------------------------------------------------------------------
# Combined Prediction
# ---------------------------------------------------------------------------


class TestCombinedPrediction:
    """Tests for predict_monthly_costs."""

    def test_predict_monthly_costs_returns_all_breakdowns(self, service: InfrastructurePricingService):
        """predict_monthly_costs returns neon, resend, llm breakdowns + grand_total."""
        mock_estimate = {
            "summarization": 1.00,
            "theme_analysis": 0.50,
            "digest_creation": 0.30,
            "historical_context": 0.20,
            "youtube_processing": 0.10,
            "total": 2.10,
        }
        mock_config = MagicMock()
        mock_config.get_cost_estimate.return_value = mock_estimate

        with patch("src.services.infrastructure_pricing_service.get_model_config", return_value=mock_config, create=True), \
             patch("src.config.models.get_model_config", return_value=mock_config):
            result = service.predict_monthly_costs(
                neon_plan="free",
                resend_plan="free",
                emails_per_month=100,
            )

        assert isinstance(result, CostPrediction)
        assert isinstance(result.neon, NeonCostBreakdown)
        assert isinstance(result.resend, ResendCostBreakdown)
        assert result.neon.plan == "free"
        assert result.resend.plan == "free"
        assert result.llm.total == 2.10

    def test_grand_total_equals_sum_of_service_totals(self, service: InfrastructurePricingService):
        """Grand total equals sum of neon.total + resend.total + llm.total."""
        mock_estimate = {
            "summarization": 5.00,
            "theme_analysis": 3.00,
            "digest_creation": 2.00,
            "historical_context": 1.00,
            "youtube_processing": 0.50,
            "total": 11.50,
        }
        mock_config = MagicMock()
        mock_config.get_cost_estimate.return_value = mock_estimate

        with patch("src.services.infrastructure_pricing_service.get_model_config", return_value=mock_config, create=True), \
             patch("src.config.models.get_model_config", return_value=mock_config):
            result = service.predict_monthly_costs(
                neon_plan="launch",
                neon_compute_hours_per_day=3,
                neon_storage_gb=10,
                neon_pitr_gb=0,
                neon_snapshot_gb=0,
                resend_plan="pro",
                emails_per_month=55000,
            )

        expected_grand = round(result.neon.total + result.resend.total + result.llm.total, 2)
        assert result.grand_total == expected_grand

        # Verify individual service totals are reasonable
        assert result.neon.total > 0
        assert result.resend.total > 0
        assert result.llm.total == 11.50


# ---------------------------------------------------------------------------
# Plan Comparison
# ---------------------------------------------------------------------------


class TestPlanComparison:
    """Tests for compare_neon_plans and compare_resend_plans."""

    def test_compare_neon_plans_recommends_free_when_usage_fits(
        self, service: InfrastructurePricingService,
    ):
        """Recommends 'free' when compute and storage fit within free tier."""
        # Free tier: 100 compute hours/month, 5 GB storage
        # 1 hour/day * 30 = 30 hours < 100, 2 GB < 5 GB
        result = service.compare_neon_plans(
            compute_hours_per_day=1,
            storage_gb=2,
        )
        assert isinstance(result, PlanComparison)
        assert result.service == "neon"
        assert result.recommended == "free"
        assert "free tier" in result.recommendation_reason.lower()
        assert "free" in result.plans
        assert result.plans["free"] == 0.0

    def test_compare_neon_plans_recommends_paid_when_exceeds_free(
        self, service: InfrastructurePricingService,
    ):
        """Recommends paid plan when usage exceeds free tier limits."""
        # 5 hours/day * 30 = 150 hours > 100 included in free
        result = service.compare_neon_plans(
            compute_hours_per_day=5,
            storage_gb=10,
        )
        assert result.recommended != "free"
        assert result.recommended in ("launch", "scale")
        assert "exceeds free tier" in result.recommendation_reason.lower()

    def test_compare_neon_plans_recommends_paid_when_storage_exceeds(
        self, service: InfrastructurePricingService,
    ):
        """Recommends paid plan when storage alone exceeds free tier."""
        # 1 hour/day (fits compute) but 10 GB > 5 GB max storage
        result = service.compare_neon_plans(
            compute_hours_per_day=1,
            storage_gb=10,
        )
        assert result.recommended != "free"

    def test_compare_neon_plans_includes_all_plans(self, service: InfrastructurePricingService):
        """All available plans are included in the comparison."""
        result = service.compare_neon_plans(compute_hours_per_day=1, storage_gb=1)
        for plan in service.get_neon_plans():
            assert plan in result.plans

    def test_compare_resend_plans_returns_cheapest(self, service: InfrastructurePricingService):
        """compare_resend_plans returns the cheapest plan."""
        # 500 emails fits in free tier
        result = service.compare_resend_plans(emails_per_month=500)
        assert isinstance(result, PlanComparison)
        assert result.service == "resend"
        assert result.recommended == "free"
        assert result.plans["free"] == 0.0
        # Pro and scale should be more expensive
        assert result.plans["pro"] >= result.plans["free"]
        assert result.plans["scale"] >= result.plans["free"]

    def test_compare_resend_plans_high_volume(self, service: InfrastructurePricingService):
        """With high volume, recommends the cheapest covering plan."""
        # 200000 emails - all plans will have overage or high base price
        result = service.compare_resend_plans(emails_per_month=200000)
        # The recommended plan should have the lowest total cost
        recommended_cost = result.plans[result.recommended]
        for plan_name, cost in result.plans.items():
            assert recommended_cost <= cost, (
                f"Recommended {result.recommended} (${recommended_cost}) "
                f"is not cheapest; {plan_name} costs ${cost}"
            )

    def test_compare_resend_plans_includes_non_enterprise(self, service: InfrastructurePricingService):
        """Enterprise plan is excluded from comparison."""
        result = service.compare_resend_plans(emails_per_month=100)
        assert "enterprise" not in result.plans
        for plan in service.get_resend_plans():
            assert plan in result.plans
