"""
Model Configuration API Routes

Endpoints for viewing and configuring which LLM model is used
for each pipeline step. Includes cost data per model.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.config.models import (
    DEFAULT_MODELS,
    MODEL_REGISTRY,
    PROVIDER_MODEL_CONFIGS,
    ModelStep,
)
from src.services.settings_service import SettingsService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/settings/models", tags=["settings"])

# Map of env var names per model step
_STEP_ENV_VARS: dict[str, str] = {step.value: f"MODEL_{step.value.upper()}" for step in ModelStep}


# ============================================================================
# Response Models
# ============================================================================


class ModelOption(BaseModel):
    """An available model with its metadata."""

    id: str
    name: str
    family: str
    supports_vision: bool
    supports_video: bool
    cost_per_mtok_input: float | None = None
    cost_per_mtok_output: float | None = None
    providers: list[str] = []


class StepConfig(BaseModel):
    """Configuration for a single pipeline step."""

    step: str
    current_model: str
    source: str  # "env" | "db" | "default"
    env_var: str
    default_model: str


class ModelSettingsResponse(BaseModel):
    """Full model settings with available models and per-step configuration."""

    steps: list[StepConfig]
    available_models: list[ModelOption]


class ModelUpdateRequest(BaseModel):
    """Request to update model for a step."""

    model_id: str


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=ModelSettingsResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_model_settings() -> ModelSettingsResponse:
    """Get model configuration for all pipeline steps.

    Returns current model per step with source indicator (env/db/default),
    plus all available models with cost data.
    """
    with get_db() as db:
        service = SettingsService(db)

        steps = []
        for step in ModelStep:
            env_var = _STEP_ENV_VARS[step.value]
            env_value = os.environ.get(env_var)
            db_value = service.get(f"model.{step.value}")
            default_value = DEFAULT_MODELS.get(step.value, "")

            if env_value and env_value in MODEL_REGISTRY:
                current = env_value
                source = "env"
            elif db_value and db_value in MODEL_REGISTRY:
                current = db_value
                source = "db"
            else:
                current = default_value
                source = "default"

            steps.append(
                StepConfig(
                    step=step.value,
                    current_model=current,
                    source=source,
                    env_var=env_var,
                    default_model=default_value,
                )
            )

        # Build available models list with cost info
        available = []
        for model_id, info in MODEL_REGISTRY.items():
            # Find providers and cost for this model
            providers = []
            cost_input = None
            cost_output = None
            for (mid, prov), pmc in PROVIDER_MODEL_CONFIGS.items():
                if mid == model_id:
                    providers.append(prov.value)
                    # Use the first provider's cost as representative
                    if cost_input is None:
                        cost_input = pmc.cost_per_mtok_input
                        cost_output = pmc.cost_per_mtok_output

            available.append(
                ModelOption(
                    id=model_id,
                    name=info.name,
                    family=info.family.value,
                    supports_vision=info.supports_vision,
                    supports_video=info.supports_video,
                    cost_per_mtok_input=cost_input,
                    cost_per_mtok_output=cost_output,
                    providers=sorted(providers),
                )
            )

        return ModelSettingsResponse(steps=steps, available_models=available)


@router.put(
    "/{step}",
    dependencies=[Depends(verify_admin_key)],
)
async def set_model_for_step(step: str, request: ModelUpdateRequest) -> dict:
    """Set the model override for a pipeline step.

    Validates:
    - Step must be a valid ModelStep
    - Model ID must exist in the model registry
    - Step must not be controlled by an env var (returns 409)
    """
    # Validate step
    try:
        ModelStep(step)
    except ValueError:
        valid = [s.value for s in ModelStep]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step: {step}. Valid steps: {valid}",
        )

    # Validate model ID
    if request.model_id not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {request.model_id}. Available: {sorted(MODEL_REGISTRY.keys())}",
        )

    # Check if controlled by env var
    env_var = _STEP_ENV_VARS[step]
    if os.environ.get(env_var):
        raise HTTPException(
            status_code=409,
            detail=f"Step '{step}' is controlled by environment variable {env_var}. "
            "Remove the env var to allow DB overrides.",
        )

    with get_db() as db:
        service = SettingsService(db)
        service.set(f"model.{step}", request.model_id)
        return {
            "step": step,
            "model_id": request.model_id,
            "source": "db",
        }


@router.delete(
    "/{step}",
    dependencies=[Depends(verify_admin_key)],
)
async def reset_model_for_step(step: str) -> dict:
    """Reset model for a step to its default."""
    try:
        ModelStep(step)
    except ValueError:
        valid = [s.value for s in ModelStep]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step: {step}. Valid steps: {valid}",
        )

    with get_db() as db:
        service = SettingsService(db)
        service.delete(f"model.{step}")
        return {
            "step": step,
            "model_id": DEFAULT_MODELS.get(step, ""),
            "source": "default",
        }
