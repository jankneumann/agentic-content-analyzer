"""API routes for LLM router evaluation and routing management.

Endpoints:
    GET    /api/v1/evaluation/datasets           — List datasets
    POST   /api/v1/evaluation/datasets           — Create dataset
    GET    /api/v1/evaluation/report              — Cost savings report
    GET    /api/v1/evaluation/routing-config      — Get routing configs
    PUT    /api/v1/evaluation/routing-config/{step} — Update routing config
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/evaluation",
    tags=["evaluation"],
    dependencies=[Depends(verify_admin_key)],
)


# ============================================================================
# Request/Response Models
# ============================================================================


class DatasetCreateRequest(BaseModel):
    """Request to create an evaluation dataset."""

    step: str = Field(..., description="Pipeline step name")
    name: str | None = Field(None, description="Optional dataset name")
    strong_model: str = Field("claude-sonnet-4-5", description="Strong model ID")
    weak_model: str = Field("claude-haiku-4-5", description="Weak model ID")


class DatasetResponse(BaseModel):
    """Evaluation dataset info."""

    id: int
    step: str
    name: str | None
    status: str
    sample_count: int
    strong_model: str
    weak_model: str


class DatasetListResponse(BaseModel):
    """List of evaluation datasets."""

    datasets: list[DatasetResponse]


class EvaluationReportItem(BaseModel):
    """Cost savings report for a single step."""

    step: str
    total_decisions: int
    pct_routed_to_weak: float
    cost_savings_vs_all_strong: float
    preference_distribution: dict
    dimension_pass_rates: dict


class EvaluationReportResponse(BaseModel):
    """Cost savings report response."""

    reports: list[EvaluationReportItem]


class RoutingConfigResponse(BaseModel):
    """Routing configuration for a step."""

    step: str
    mode: str
    enabled: bool
    threshold: float
    strong_model: str | None
    weak_model: str | None


class RoutingConfigUpdateRequest(BaseModel):
    """Request to update routing config for a step."""

    mode: str | None = Field(None, description="Routing mode: 'fixed' or 'dynamic'")
    enabled: bool | None = Field(None, description="Whether dynamic routing is enabled")
    threshold: float | None = Field(None, description="Complexity threshold (0.0-1.0)")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(step: str | None = None):
    """List evaluation datasets, optionally filtered by step."""
    from src.services.evaluation_service import EvaluationService

    with get_db() as db:
        svc = EvaluationService(db_session=db)
        datasets = svc.get_datasets(step=step)

    return DatasetListResponse(
        datasets=[
            DatasetResponse(
                id=ds.id,
                step=ds.step,
                name=ds.name,
                status=ds.status,
                sample_count=ds.sample_count,
                strong_model=ds.strong_model,
                weak_model=ds.weak_model,
            )
            for ds in datasets
        ]
    )


@router.post("/datasets", response_model=DatasetResponse, status_code=201)
async def create_dataset(request: DatasetCreateRequest):
    """Create a new evaluation dataset."""
    from src.services.evaluation_service import EvaluationService

    with get_db() as db:
        svc = EvaluationService(db_session=db)
        ds = svc.create_dataset(
            step=request.step,
            name=request.name,
            strong_model=request.strong_model,
            weak_model=request.weak_model,
        )
        db.commit()
    return DatasetResponse(
        id=ds.id,
        step=ds.step,
        name=ds.name,
        status=ds.status,
        sample_count=ds.sample_count,
        strong_model=ds.strong_model,
        weak_model=ds.weak_model,
    )


@router.get("/report", response_model=EvaluationReportResponse)
async def get_report(step: str | None = None):
    """Generate cost savings report from routing decisions."""
    from src.services.evaluation_service import EvaluationService

    with get_db() as db:
        svc = EvaluationService(db_session=db)
        reports = svc.generate_report(step=step)

    return EvaluationReportResponse(
        reports=[
            EvaluationReportItem(
                step=r.step,
                total_decisions=r.total_decisions,
                pct_routed_to_weak=r.pct_routed_to_weak,
                cost_savings_vs_all_strong=r.cost_savings_vs_all_strong,
                preference_distribution=r.preference_distribution,
                dimension_pass_rates=r.dimension_pass_rates,
            )
            for r in reports
        ]
    )


@router.get("/routing-config")
async def list_routing_configs():
    """Get routing configuration for all steps."""
    from src.config.models import ModelConfig, ModelStep

    config = ModelConfig()
    configs = []
    for step in ModelStep:
        rc = config.get_routing_config(step)
        configs.append(
            RoutingConfigResponse(
                step=rc.step,
                mode=rc.mode,
                enabled=rc.enabled,
                threshold=rc.threshold,
                strong_model=rc.strong_model,
                weak_model=rc.weak_model,
            )
        )
    return {"configs": configs}


@router.put("/routing-config/{step}")
async def update_routing_config(step: str, request: RoutingConfigUpdateRequest):
    """Update routing configuration for a step.

    Persists to the routing_configs DB table. Falls back to in-memory
    config for the response if the step doesn't exist yet in DB.
    """
    from src.config.models import ModelConfig, ModelStep, RoutingMode
    from src.models.evaluation import RoutingConfig as RoutingConfigRecord

    try:
        model_step = ModelStep(step)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown step: {step}")

    # Validate inputs before touching DB
    if request.mode is not None:
        try:
            RoutingMode(request.mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {request.mode}. Must be 'fixed' or 'dynamic'.",
            )

    if request.threshold is not None and not 0.0 <= request.threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="Threshold must be between 0.0 and 1.0",
        )

    with get_db() as db:
        record = db.query(RoutingConfigRecord).filter_by(step=step).first()
        if not record:
            # Create from current in-memory defaults
            config = ModelConfig()
            rc = config.get_routing_config(model_step)
            record = RoutingConfigRecord(
                step=step,
                mode=rc.mode,
                enabled=rc.enabled,
                threshold=rc.threshold,
                strong_model=rc.strong_model,
                weak_model=rc.weak_model,
            )
            db.add(record)

        if request.mode is not None:
            record.mode = request.mode
        if request.enabled is not None:
            record.enabled = request.enabled
        if request.threshold is not None:
            record.threshold = request.threshold
        db.commit()

        return RoutingConfigResponse(
            step=record.step,
            mode=record.mode,
            enabled=record.enabled,
            threshold=record.threshold,
            strong_model=record.strong_model,
            weak_model=record.weak_model,
        )
