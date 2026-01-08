"""
Settings API Routes

Endpoints for managing application settings including:
- Prompt overrides for chat and pipeline steps
- Future: model preferences, feature flags, etc.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.settings import PromptOverride
from src.services.prompt_service import PromptService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PromptInfo(BaseModel):
    """Information about a prompt with override status."""

    key: str
    category: str
    name: str
    default_value: str
    current_value: str
    has_override: bool


class PromptListResponse(BaseModel):
    """Response containing all prompts with override status."""

    prompts: list[PromptInfo]


class PromptUpdateRequest(BaseModel):
    """Request to update a prompt override."""

    value: str | None = Field(
        None,
        description="New prompt value. Set to null to clear override and revert to default.",
    )


class PromptUpdateResponse(BaseModel):
    """Response after updating a prompt."""

    key: str
    current_value: str
    has_override: bool


# ============================================================================
# Prompt Endpoints
# ============================================================================


@router.get("/prompts", response_model=PromptListResponse)
async def list_prompts() -> PromptListResponse:
    """Get all prompts with their current values and override status.

    Returns prompts organized by category (chat, pipeline) with:
    - default_value: The value from prompts.yaml
    - current_value: The effective value (override if exists, else default)
    - has_override: Whether this prompt has a user override
    """
    with get_db() as db:
        prompt_service = PromptService(db)
        defaults = prompt_service._defaults

        prompts = []

        # Chat prompts
        chat_prompts = defaults.get("chat", {})
        for artifact_type, prompt_data in chat_prompts.items():
            key = f"chat.{artifact_type}.system"
            default_value = prompt_data.get("system", "")

            # Check for override
            override = db.query(PromptOverride).filter_by(key=key).first()

            prompts.append(
                PromptInfo(
                    key=key,
                    category="chat",
                    name=f"{artifact_type.title()} Chat System Prompt",
                    default_value=default_value,
                    current_value=override.value if override else default_value,
                    has_override=override is not None,
                )
            )

        # Pipeline prompts
        pipeline_prompts = defaults.get("pipeline", {})
        for step_name, prompt_data in pipeline_prompts.items():
            key = f"pipeline.{step_name}.system"
            default_value = prompt_data.get("system", "")

            # Check for override
            override = db.query(PromptOverride).filter_by(key=key).first()

            # Format step name for display
            display_name = step_name.replace("_", " ").title()

            prompts.append(
                PromptInfo(
                    key=key,
                    category="pipeline",
                    name=f"{display_name} System Prompt",
                    default_value=default_value,
                    current_value=override.value if override else default_value,
                    has_override=override is not None,
                )
            )

        return PromptListResponse(prompts=prompts)


@router.get("/prompts/{key:path}", response_model=PromptInfo)
async def get_prompt(key: str) -> PromptInfo:
    """Get a specific prompt by key.

    Key format: category.name.prompt_type (e.g., "chat.summary.system")
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Parse key to get default value
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        category, name, prompt_type = parts[0], parts[1], ".".join(parts[2:])

        # Get default from config
        defaults = prompt_service._defaults
        category_defaults = defaults.get(category, {})
        name_defaults = category_defaults.get(name, {})
        default_value = name_defaults.get(prompt_type, "")

        if not default_value and category_defaults:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        # Check for override
        override = db.query(PromptOverride).filter_by(key=key).first()

        # Format display name
        display_name = name.replace("_", " ").title()

        return PromptInfo(
            key=key,
            category=category,
            name=f"{display_name} {prompt_type.title()} Prompt",
            default_value=default_value,
            current_value=override.value if override else default_value,
            has_override=override is not None,
        )


@router.put("/prompts/{key:path}", response_model=PromptUpdateResponse)
async def update_prompt(key: str, request: PromptUpdateRequest) -> PromptUpdateResponse:
    """Update or clear a prompt override.

    - Set value to a string to create/update an override
    - Set value to null to clear the override and revert to default
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Validate key exists in defaults
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        category, name, prompt_type = parts[0], parts[1], ".".join(parts[2:])

        defaults = prompt_service._defaults
        category_defaults = defaults.get(category, {})
        name_defaults = category_defaults.get(name, {})
        default_value = name_defaults.get(prompt_type, "")

        # Validate the prompt exists in defaults
        if not default_value:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        if request.value is None:
            # Clear override
            prompt_service.clear_override(key)
            return PromptUpdateResponse(
                key=key,
                current_value=default_value,
                has_override=False,
            )
        else:
            # Set override
            prompt_service.set_override(key, request.value)
            return PromptUpdateResponse(
                key=key,
                current_value=request.value,
                has_override=True,
            )


@router.delete("/prompts/{key:path}", response_model=PromptUpdateResponse)
async def reset_prompt(key: str) -> PromptUpdateResponse:
    """Reset a prompt override to its default value.

    Alias for PUT with value=null.
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Parse key to get default value
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        category, name, prompt_type = parts[0], parts[1], ".".join(parts[2:])

        defaults = prompt_service._defaults
        category_defaults = defaults.get(category, {})
        name_defaults = category_defaults.get(name, {})
        default_value = name_defaults.get(prompt_type, "")

        # Clear override
        prompt_service.clear_override(key)

        return PromptUpdateResponse(
            key=key,
            current_value=default_value,
            has_override=False,
        )
