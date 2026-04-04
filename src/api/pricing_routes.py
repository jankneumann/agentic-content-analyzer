"""
Infrastructure Cost Prediction API Routes

Endpoints for estimating monthly costs across Neon (database),
Resend (email), and LLM services.  All parameters are optional
and fall back to sensible defaults from settings/pricing.yaml.

Includes pricing extraction endpoints that scrape Neon/Resend pricing
pages and diff against the current pricing.yaml (mirroring the model
pricing extraction workflow).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.services.infrastructure_pricing_service import (
    CostPrediction,
    InfrastructurePricingService,
    NeonCostBreakdown,
    PlanComparison,
    ResendCostBreakdown,
)

router = APIRouter(
    prefix="/api/v1/pricing",
    tags=["pricing"],
    dependencies=[Depends(verify_admin_key)],
)


def _get_service() -> InfrastructurePricingService:
    return InfrastructurePricingService()


# ---------------------------------------------------------------------------
# Combined prediction
# ---------------------------------------------------------------------------


@router.get(
    "/predict",
    response_model=CostPrediction,
    summary="Predict total monthly infrastructure costs",
)
async def predict_monthly_costs(
    # Neon
    neon_plan: str | None = Query(None, description="Neon plan: free, launch, or scale"),
    neon_compute_hours_per_day: float | None = Query(None, description="Average daily Neon compute hours"),
    neon_storage_gb: float | None = Query(None, description="Neon storage in GB"),
    neon_pitr_gb: float | None = Query(None, description="Neon PITR history storage in GB"),
    neon_snapshot_gb: float | None = Query(None, description="Neon snapshot storage in GB"),
    # Resend
    resend_plan: str | None = Query(None, description="Resend plan: free, pro, or scale"),
    emails_per_month: int | None = Query(None, description="Expected emails per month"),
    # LLM
    content_items_per_day: int = Query(10, description="Content items ingested per day"),
    digests_per_week: int = Query(2, description="Digests generated per week"),
    youtube_videos_per_week: int = Query(5, description="YouTube videos processed per week"),
) -> CostPrediction:
    """Predict total monthly costs across Neon, Resend, and LLM services.

    All parameters are optional.  Defaults come from settings/pricing.yaml
    and the model configuration in settings/models.yaml.
    """
    service = _get_service()
    return service.predict_monthly_costs(
        neon_plan=neon_plan,
        neon_compute_hours_per_day=neon_compute_hours_per_day,
        neon_storage_gb=neon_storage_gb,
        neon_pitr_gb=neon_pitr_gb,
        neon_snapshot_gb=neon_snapshot_gb,
        resend_plan=resend_plan,
        emails_per_month=emails_per_month,
        content_items_per_day=content_items_per_day,
        digests_per_week=digests_per_week,
        youtube_videos_per_week=youtube_videos_per_week,
    )


# ---------------------------------------------------------------------------
# Per-service estimates
# ---------------------------------------------------------------------------


@router.get(
    "/neon",
    response_model=NeonCostBreakdown,
    summary="Estimate monthly Neon database costs",
)
async def estimate_neon_cost(
    plan: str | None = Query(None, description="Neon plan tier"),
    compute_hours_per_day: float | None = Query(None, description="Average daily compute hours"),
    storage_gb: float | None = Query(None, description="Storage in GB"),
    pitr_gb: float | None = Query(None, description="PITR history storage in GB"),
    snapshot_gb: float | None = Query(None, description="Snapshot storage in GB"),
) -> NeonCostBreakdown:
    """Estimate monthly Neon Postgres costs for the given usage profile."""
    service = _get_service()
    return service.estimate_neon_cost(
        plan=plan,
        compute_hours_per_day=compute_hours_per_day,
        storage_gb=storage_gb,
        pitr_gb=pitr_gb,
        snapshot_gb=snapshot_gb,
    )


@router.get(
    "/resend",
    response_model=ResendCostBreakdown,
    summary="Estimate monthly Resend email costs",
)
async def estimate_resend_cost(
    plan: str | None = Query(None, description="Resend plan tier"),
    emails_per_month: int | None = Query(None, description="Expected monthly email volume"),
) -> ResendCostBreakdown:
    """Estimate monthly Resend email delivery costs for the given volume."""
    service = _get_service()
    return service.estimate_resend_cost(
        plan=plan,
        emails_per_month=emails_per_month,
    )


# ---------------------------------------------------------------------------
# Plan comparisons
# ---------------------------------------------------------------------------


@router.get(
    "/neon/compare",
    response_model=PlanComparison,
    summary="Compare Neon plans for a usage profile",
)
async def compare_neon_plans(
    compute_hours_per_day: float | None = Query(None, description="Average daily compute hours"),
    storage_gb: float | None = Query(None, description="Storage in GB"),
    pitr_gb: float | None = Query(None, description="PITR history storage in GB"),
    snapshot_gb: float | None = Query(None, description="Snapshot storage in GB"),
) -> PlanComparison:
    """Compare costs across all Neon plans for the same usage profile.

    Returns per-plan costs and a recommendation.
    """
    service = _get_service()
    return service.compare_neon_plans(
        compute_hours_per_day=compute_hours_per_day,
        storage_gb=storage_gb,
        pitr_gb=pitr_gb,
        snapshot_gb=snapshot_gb,
    )


@router.get(
    "/resend/compare",
    response_model=PlanComparison,
    summary="Compare Resend plans for an email volume",
)
async def compare_resend_plans(
    emails_per_month: int | None = Query(None, description="Expected monthly email volume"),
) -> PlanComparison:
    """Compare costs across all Resend plans for the same email volume.

    Returns per-plan costs and a recommendation.
    """
    service = _get_service()
    return service.compare_resend_plans(emails_per_month=emails_per_month)


# ---------------------------------------------------------------------------
# Pricing extraction (refresh from live pages)
# ---------------------------------------------------------------------------


class PricingRefreshRequest(BaseModel):
    """Request body for triggering a pricing refresh."""

    services: list[str] | None = None  # ["neon", "resend"] or None for all
    dry_run: bool = True


class InfraPricingDiffItem(BaseModel):
    """A single field-level change detected during refresh."""

    service: str
    plan: str
    field: str
    current_value: object
    extracted_value: object


class InfraPricingRefreshReport(BaseModel):
    """Result of an infrastructure pricing refresh."""

    services_fetched: list[str] = []
    services_failed: list[str] = []
    diffs: list[InfraPricingDiffItem] = []
    new_plans: list[dict] = []
    errors: list[str] = []
    applied: bool = False
    timestamp: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.diffs) or bool(self.new_plans)


# Module-level state for last refresh (mirrors model pricing pattern)
_last_infra_refresh: InfraPricingRefreshReport | None = None


@router.post(
    "/refresh",
    response_model=InfraPricingRefreshReport,
    summary="Refresh Neon/Resend pricing from live pages",
)
async def refresh_pricing(request: PricingRefreshRequest) -> InfraPricingRefreshReport:
    """Fetch latest pricing from Neon and Resend pages, extract via LLM, and diff.

    Uses the same fetch + LLM extraction pattern as the model pricing extractor.
    Tries agent-friendly .md URLs first, then falls back to HTML pages.

    By default runs in dry_run mode (preview only). Set dry_run=false to apply
    changes to settings/pricing.yaml.
    """
    global _last_infra_refresh

    from src.services.infrastructure_pricing_extractor import InfrastructurePricingExtractor

    extractor = InfrastructurePricingExtractor()
    report = await extractor.run(services=request.services, dry_run=request.dry_run)

    result = InfraPricingRefreshReport(
        services_fetched=report.services_fetched,
        services_failed=report.services_failed,
        diffs=[
            InfraPricingDiffItem(
                service=d.service,
                plan=d.plan,
                field=d.field,
                current_value=d.current_value,
                extracted_value=d.extracted_value,
            )
            for d in report.diffs
        ],
        new_plans=report.new_plans,
        errors=report.extraction_errors,
        applied=report.applied,
        timestamp=report.timestamp,
    )

    _last_infra_refresh = result
    return result


@router.get(
    "/refresh/status",
    response_model=InfraPricingRefreshReport | None,
    summary="Get last pricing refresh status",
)
async def get_refresh_status() -> InfraPricingRefreshReport | dict:
    """Get the result of the last infrastructure pricing refresh, if any."""
    if not _last_infra_refresh:
        return {"message": "No infrastructure pricing refresh has been executed yet"}
    return _last_infra_refresh
