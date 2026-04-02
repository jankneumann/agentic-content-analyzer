"""
Model Registry API Routes

Endpoints for querying the model catalog, comparing provider pricing,
and triggering automated pricing extraction from provider pages.

Complements model_settings_routes.py (which manages model-per-step assignments)
by focusing on the registry catalog and pricing data.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.services.model_registry_service import (
    ModelDetail,
    ModelRegistryService,
    ModelSummary,
    PricingRefreshReport,
)

router = APIRouter(
    prefix="/api/v1/models",
    tags=["models"],
    dependencies=[Depends(verify_admin_key)],
)

_service = ModelRegistryService()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PricingRefreshRequest(BaseModel):
    """Request body for triggering a pricing refresh."""

    providers: list[str] | None = None
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Response models (thin wrappers for list endpoints)
# ---------------------------------------------------------------------------


class ModelListResponse(BaseModel):
    models: list[ModelSummary]
    count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List all models in the registry",
)
async def list_models(
    family: str | None = Query(None, description="Filter by model family (claude, gemini, gpt)"),
) -> ModelListResponse:
    """List all models with their capabilities and default pricing.

    Optionally filter by model family.
    """
    models = _service.list_models(family=family)
    return ModelListResponse(models=models, count=len(models))


@router.get(
    "/{model_id}",
    response_model=ModelDetail,
    summary="Get model details with provider pricing",
)
async def get_model(model_id: str) -> ModelDetail:
    """Get detailed information about a specific model including per-provider pricing."""
    detail = _service.get_model(model_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return detail


@router.get(
    "/{model_id}/pricing",
    summary="Get pricing breakdown for a model across providers",
)
async def get_model_pricing(model_id: str) -> dict:
    """Get pricing comparison for a model across all available providers."""
    detail = _service.get_model(model_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return {
        "model_id": model_id,
        "providers": [p.model_dump() for p in detail.provider_pricing],
    }


@router.post(
    "/pricing/refresh",
    response_model=PricingRefreshReport,
    summary="Trigger pricing extraction from provider pages",
)
async def refresh_pricing(request: PricingRefreshRequest) -> PricingRefreshReport:
    """Fetch latest pricing from provider pages and diff against the registry.

    Uses LLM-based extraction to parse pricing tables from Anthropic, OpenAI,
    Google AI, and AWS Bedrock pricing pages.

    By default runs in dry_run mode (preview only). Set dry_run=false to apply.
    """
    return await _service.refresh_pricing(
        providers=request.providers,
        dry_run=request.dry_run,
    )


@router.get(
    "/pricing/status",
    response_model=PricingRefreshReport | None,
    summary="Get last pricing refresh status",
)
async def get_pricing_status() -> PricingRefreshReport | dict:
    """Get the result of the last pricing refresh, if any."""
    report = _service.get_last_refresh()
    if not report:
        return {"message": "No pricing refresh has been executed yet"}
    return report
