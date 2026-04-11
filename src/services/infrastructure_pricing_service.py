"""Infrastructure cost prediction service for Neon and Resend.

Loads pricing tiers from settings/pricing.yaml and combines them with
LLM cost estimates from ModelConfig to produce a total monthly cost
prediction for running the newsletter aggregator.

Usage:
    from src.services.infrastructure_pricing_service import InfrastructurePricingService

    service = InfrastructurePricingService()
    prediction = service.predict_monthly_costs(
        neon_plan="launch",
        neon_compute_hours_per_day=3,
        neon_storage_gb=10,
        resend_plan="free",
        emails_per_month=800,
        content_items_per_day=15,
    )
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class NeonCostBreakdown(BaseModel):
    """Neon Postgres cost breakdown."""

    plan: str
    base_price: float
    compute_cost: float
    storage_cost: float
    pitr_cost: float
    snapshot_cost: float
    total: float
    # Usage inputs echoed back
    compute_hours_per_month: float
    storage_gb: float
    pitr_gb: float
    snapshot_gb: float


class ResendCostBreakdown(BaseModel):
    """Resend email cost breakdown."""

    plan: str
    base_price: float
    overage_cost: float
    total: float
    # Usage inputs echoed back
    emails_per_month: int
    included_emails: int
    overage_emails: int


class LLMCostBreakdown(BaseModel):
    """LLM cost breakdown (from ModelConfig.get_cost_estimate)."""

    summarization: float
    theme_analysis: float
    digest_creation: float
    historical_context: float
    youtube_processing: float
    total: float


class CostPrediction(BaseModel):
    """Full monthly cost prediction across all services."""

    neon: NeonCostBreakdown
    resend: ResendCostBreakdown
    llm: LLMCostBreakdown
    grand_total: float


class PlanComparison(BaseModel):
    """Cost comparison across plan tiers for a single service."""

    service: str
    plans: dict[str, float]  # plan_name -> monthly cost
    recommended: str
    recommendation_reason: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _load_pricing_yaml() -> dict[str, Any]:
    """Load pricing configuration from YAML."""
    # Try ConfigRegistry first
    try:
        from src.config.config_registry import get_config_registry

        registry = get_config_registry()
        if "pricing" in registry.registered_domains:
            return registry.get_raw("pricing")
    except (ImportError, ValueError, FileNotFoundError):
        pass

    # Fallback: direct file read
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            yaml_path = parent / "settings" / "pricing.yaml"
            if yaml_path.exists():
                with open(yaml_path) as f:
                    return yaml.safe_load(f)
            break

    raise FileNotFoundError("settings/pricing.yaml not found")


class InfrastructurePricingService:
    """Calculates cost predictions for Neon, Resend, and LLM usage."""

    def __init__(self) -> None:
        self._config = _load_pricing_yaml()
        self._neon = self._config["neon"]
        self._resend = self._config["resend"]

    # -- Neon -----------------------------------------------------------------

    def get_neon_plans(self) -> list[str]:
        """Return available Neon plan names."""
        return list(self._neon["plans"].keys())

    def estimate_neon_cost(
        self,
        plan: str | None = None,
        compute_hours_per_day: float | None = None,
        storage_gb: float | None = None,
        pitr_gb: float | None = None,
        snapshot_gb: float | None = None,
    ) -> NeonCostBreakdown:
        """Estimate monthly Neon costs.

        Args:
            plan: Neon plan tier (free/launch/scale). Defaults to config default.
            compute_hours_per_day: Average daily compute hours.
            storage_gb: Total storage in GB.
            pitr_gb: Point-in-time recovery storage in GB.
            snapshot_gb: Snapshot storage in GB.

        Returns:
            Detailed cost breakdown.
        """
        defaults = self._neon["defaults"]
        plan = plan or defaults["plan"]
        compute_hours_per_day = (
            compute_hours_per_day
            if compute_hours_per_day is not None
            else defaults["avg_compute_hours_per_day"]
        )
        storage_gb = storage_gb if storage_gb is not None else defaults["storage_gb"]
        pitr_gb = pitr_gb if pitr_gb is not None else defaults["pitr_gb"]
        snapshot_gb = snapshot_gb if snapshot_gb is not None else defaults["snapshot_gb"]

        plan_config = self._neon["plans"].get(plan)
        if not plan_config:
            raise ValueError(f"Unknown Neon plan: {plan}. Available: {self.get_neon_plans()}")

        monthly_compute_hours = compute_hours_per_day * 30

        if plan == "free":
            # Free plan: no charges beyond included resources
            return NeonCostBreakdown(
                plan=plan,
                base_price=0.0,
                compute_cost=0.0,
                storage_cost=0.0,
                pitr_cost=0.0,
                snapshot_cost=0.0,
                total=0.0,
                compute_hours_per_month=min(
                    monthly_compute_hours, plan_config["included_compute_hours"]
                ),
                storage_gb=min(storage_gb, plan_config["max_storage_gb"]),
                pitr_gb=0.0,
                snapshot_gb=0.0,
            )

        # Paid plans: usage-based with minimum spend
        compute_cost = monthly_compute_hours * plan_config["cost_per_compute_hour"]

        # Storage: tiered pricing (first 50 GB at one rate, rest at another)
        if storage_gb <= 50:
            storage_cost = storage_gb * plan_config["cost_per_storage_gb"]
        else:
            storage_cost = (
                50 * plan_config["cost_per_storage_gb"]
                + (storage_gb - 50) * plan_config["cost_per_storage_gb_over_50"]
            )

        pitr_cost = pitr_gb * plan_config["cost_per_pitr_gb"]
        snapshot_cost = snapshot_gb * plan_config["cost_per_snapshot_gb"]

        usage_total = compute_cost + storage_cost + pitr_cost + snapshot_cost
        # Minimum spend rule: you pay whichever is higher
        total = max(usage_total, plan_config["monthly_price"])

        return NeonCostBreakdown(
            plan=plan,
            base_price=plan_config["monthly_price"],
            compute_cost=round(compute_cost, 4),
            storage_cost=round(storage_cost, 4),
            pitr_cost=round(pitr_cost, 4),
            snapshot_cost=round(snapshot_cost, 4),
            total=round(total, 2),
            compute_hours_per_month=monthly_compute_hours,
            storage_gb=storage_gb,
            pitr_gb=pitr_gb,
            snapshot_gb=snapshot_gb,
        )

    # -- Resend ---------------------------------------------------------------

    def get_resend_plans(self) -> list[str]:
        """Return available Resend plan names."""
        return [p for p in self._resend["plans"].keys() if p != "enterprise"]

    def estimate_resend_cost(
        self,
        plan: str | None = None,
        emails_per_month: int | None = None,
    ) -> ResendCostBreakdown:
        """Estimate monthly Resend costs.

        Args:
            plan: Resend plan tier (free/pro/scale). Defaults to config default.
            emails_per_month: Expected monthly email volume.

        Returns:
            Detailed cost breakdown.
        """
        defaults = self._resend["defaults"]
        plan = plan or defaults["plan"]
        emails_per_month = (
            emails_per_month if emails_per_month is not None else defaults["emails_per_month"]
        )

        plan_config = self._resend["plans"].get(plan)
        if not plan_config:
            raise ValueError(f"Unknown Resend plan: {plan}. Available: {self.get_resend_plans()}")

        base_price = plan_config["monthly_price"] or 0.0
        included = plan_config["emails_per_month"] or 0

        overage_emails = max(0, emails_per_month - included)
        overage_cost = 0.0

        if overage_emails > 0 and plan_config.get("pay_as_you_go"):
            overage_rate = plan_config.get("overage_per_1000_emails", 0)
            # Billed in buckets of 1,000
            buckets = math.ceil(overage_emails / 1000)
            overage_cost = buckets * overage_rate

        return ResendCostBreakdown(
            plan=plan,
            base_price=base_price,
            overage_cost=round(overage_cost, 2),
            total=round(base_price + overage_cost, 2),
            emails_per_month=emails_per_month,
            included_emails=included,
            overage_emails=overage_emails,
        )

    # -- LLM (delegates to ModelConfig) ---------------------------------------

    def estimate_llm_cost(
        self,
        content_items_per_day: int = 10,
        digests_per_week: int = 2,
        youtube_videos_per_week: int = 5,
    ) -> LLMCostBreakdown:
        """Estimate monthly LLM costs using ModelConfig.

        Wraps ModelConfig.get_cost_estimate() into a structured response.
        Returns zeroed breakdown if no providers are configured (e.g., test environments).
        """
        try:
            from src.config.models import get_model_config

            config = get_model_config()
            estimate = config.get_cost_estimate(
                content_items_per_day=content_items_per_day,
                digests_per_week=digests_per_week,
                youtube_videos_per_week=youtube_videos_per_week,
            )

            return LLMCostBreakdown(
                summarization=round(estimate["summarization"], 4),
                theme_analysis=round(estimate["theme_analysis"], 4),
                digest_creation=round(estimate["digest_creation"], 4),
                historical_context=round(estimate["historical_context"], 4),
                youtube_processing=round(estimate["youtube_processing"], 4),
                total=round(estimate["total"], 4),
            )
        except (ValueError, ImportError):
            # No providers configured (test env) or config unavailable
            logger.debug("LLM cost estimation unavailable, returning zeros")
            return LLMCostBreakdown(
                summarization=0.0,
                theme_analysis=0.0,
                digest_creation=0.0,
                historical_context=0.0,
                youtube_processing=0.0,
                total=0.0,
            )

    # -- Combined prediction --------------------------------------------------

    def predict_monthly_costs(
        self,
        # Neon params
        neon_plan: str | None = None,
        neon_compute_hours_per_day: float | None = None,
        neon_storage_gb: float | None = None,
        neon_pitr_gb: float | None = None,
        neon_snapshot_gb: float | None = None,
        # Resend params
        resend_plan: str | None = None,
        emails_per_month: int | None = None,
        # LLM params
        content_items_per_day: int = 10,
        digests_per_week: int = 2,
        youtube_videos_per_week: int = 5,
    ) -> CostPrediction:
        """Predict total monthly infrastructure costs.

        Combines Neon database, Resend email, and LLM API costs into a
        single prediction. All parameters are optional and fall back to
        sensible defaults from pricing.yaml.

        Returns:
            Full cost prediction with per-service breakdowns.
        """
        neon = self.estimate_neon_cost(
            plan=neon_plan,
            compute_hours_per_day=neon_compute_hours_per_day,
            storage_gb=neon_storage_gb,
            pitr_gb=neon_pitr_gb,
            snapshot_gb=neon_snapshot_gb,
        )
        resend = self.estimate_resend_cost(
            plan=resend_plan,
            emails_per_month=emails_per_month,
        )
        llm = self.estimate_llm_cost(
            content_items_per_day=content_items_per_day,
            digests_per_week=digests_per_week,
            youtube_videos_per_week=youtube_videos_per_week,
        )

        grand_total = round(neon.total + resend.total + llm.total, 2)

        return CostPrediction(
            neon=neon,
            resend=resend,
            llm=llm,
            grand_total=grand_total,
        )

    # -- Plan comparison helpers ----------------------------------------------

    def compare_neon_plans(
        self,
        compute_hours_per_day: float | None = None,
        storage_gb: float | None = None,
        pitr_gb: float | None = None,
        snapshot_gb: float | None = None,
    ) -> PlanComparison:
        """Compare costs across Neon plans for the same usage profile."""
        costs: dict[str, float] = {}
        for plan_name in self.get_neon_plans():
            breakdown = self.estimate_neon_cost(
                plan=plan_name,
                compute_hours_per_day=compute_hours_per_day,
                storage_gb=storage_gb,
                pitr_gb=pitr_gb,
                snapshot_gb=snapshot_gb,
            )
            costs[plan_name] = breakdown.total

        # Find cheapest paid plan (free may have resource limits)
        paid_plans = {k: v for k, v in costs.items() if k != "free"}
        cheapest_paid = min(paid_plans, key=paid_plans.get) if paid_plans else "free"

        # Recommend free if usage fits, otherwise cheapest paid
        defaults = self._neon["defaults"]
        ch = (
            compute_hours_per_day
            if compute_hours_per_day is not None
            else defaults["avg_compute_hours_per_day"]
        )
        sg = storage_gb if storage_gb is not None else defaults["storage_gb"]
        free_plan = self._neon["plans"]["free"]

        if (ch * 30) <= free_plan["included_compute_hours"] and sg <= free_plan["max_storage_gb"]:
            recommended = "free"
            reason = "Usage fits within free tier limits"
        else:
            recommended = cheapest_paid
            reason = (
                f"Usage exceeds free tier; {cheapest_paid} is the most cost-effective paid plan"
            )

        return PlanComparison(
            service="neon",
            plans=costs,
            recommended=recommended,
            recommendation_reason=reason,
        )

    def compare_resend_plans(
        self,
        emails_per_month: int | None = None,
    ) -> PlanComparison:
        """Compare costs across Resend plans for the same usage profile."""
        defaults = self._resend["defaults"]
        volume = emails_per_month if emails_per_month is not None else defaults["emails_per_month"]

        costs: dict[str, float] = {}
        for plan_name in self.get_resend_plans():
            breakdown = self.estimate_resend_cost(
                plan=plan_name,
                emails_per_month=volume,
            )
            costs[plan_name] = breakdown.total

        # Simple recommendation: cheapest plan that covers the volume
        recommended = min(costs, key=costs.get)
        free_limit = self._resend["plans"]["free"]["emails_per_month"]

        if volume <= free_limit:
            reason = f"Free tier covers {volume} emails/month (limit: {free_limit})"
        else:
            reason = f"{recommended} plan is the most cost-effective for {volume} emails/month"

        return PlanComparison(
            service="resend",
            plans=costs,
            recommended=recommended,
            recommendation_reason=reason,
        )
