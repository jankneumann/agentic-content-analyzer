"""
Settings API Routes

Endpoints for managing application settings including:
- Prompt overrides for chat and pipeline steps
- Prompt testing with template rendering
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
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
    version: int | None = None
    description: str | None = None


class PromptListResponse(BaseModel):
    """Response containing all prompts with override status."""

    prompts: list[PromptInfo]


class PromptUpdateRequest(BaseModel):
    """Request to update a prompt override."""

    value: str | None = Field(
        None,
        description="New prompt value. Set to null to clear override and revert to default.",
    )
    description: str | None = Field(
        None,
        description="Optional description of the change.",
    )


class PromptUpdateResponse(BaseModel):
    """Response after updating a prompt."""

    key: str
    current_value: str
    has_override: bool
    version: int | None = None


class PromptTestRequest(BaseModel):
    """Request to test a prompt template."""

    draft_value: str | None = Field(
        None,
        description="Draft prompt value to test (without saving). "
        "If omitted, uses current value (override or default).",
    )
    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Template variables to substitute.",
    )


class PromptTestResponse(BaseModel):
    """Response from testing a prompt template."""

    rendered_prompt: str
    variable_names: list[str]


# ============================================================================
# Prompt Endpoints
# ============================================================================


@router.get(
    "/prompts",
    response_model=PromptListResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def list_prompts() -> PromptListResponse:
    """Get all prompts with their current values and override status.

    Walks the full YAML tree to enumerate all leaf-node prompts, including
    template variants like length_brief, user_template, etc.
    """
    with get_db() as db:
        prompt_service = PromptService(db)
        all_prompts = prompt_service.list_all_prompts()

        prompts = []
        for p in all_prompts:
            display_name = p["step"].replace("_", " ").title()
            prompt_name = p["name"].replace("_", " ").title()

            prompts.append(
                PromptInfo(
                    key=p["key"],
                    category=p["category"],
                    name=f"{display_name} {prompt_name} Prompt",
                    default_value=p["default"],
                    current_value=p["override"] if p["has_override"] else p["default"],
                    has_override=p["has_override"],
                    version=p["version"],
                    description=p["description"],
                )
            )

        return PromptListResponse(prompts=prompts)


@router.get(
    "/prompts/{key:path}",
    response_model=PromptInfo,
    dependencies=[Depends(verify_admin_key)],
)
async def get_prompt(key: str) -> PromptInfo:
    """Get a specific prompt by key.

    Key format: category.step.prompt_name (e.g., "chat.summary.system")
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Parse key
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        category, step, prompt_name = parts[0], parts[1], ".".join(parts[2:])

        # Get default from config
        default_value = prompt_service.get_default(key)

        if not default_value:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        # Check for override
        override = prompt_service.get_override(key)

        # Format display name
        display_name = step.replace("_", " ").title()

        return PromptInfo(
            key=key,
            category=category,
            name=f"{display_name} {prompt_name.replace('_', ' ').title()} Prompt",
            default_value=default_value,
            current_value=override.value if override else default_value,
            has_override=override is not None,
            version=override.version if override else None,
            description=override.description if override else None,
        )


@router.put(
    "/prompts/{key:path}",
    response_model=PromptUpdateResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def update_prompt(key: str, request: PromptUpdateRequest) -> PromptUpdateResponse:
    """Update or clear a prompt override.

    - Set value to a string to create/update an override
    - Set value to null to clear the override and revert to default
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Validate key format
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        # Validate the prompt exists in defaults
        default_value = prompt_service.get_default(key)
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
            prompt_service.set_override(key, request.value, description=request.description)
            override = prompt_service.get_override(key)
            return PromptUpdateResponse(
                key=key,
                current_value=request.value,
                has_override=True,
                version=override.version if override else 1,
            )


@router.delete(
    "/prompts/{key:path}",
    response_model=PromptUpdateResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def reset_prompt(key: str) -> PromptUpdateResponse:
    """Reset a prompt override to its default value.

    Alias for PUT with value=null.
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Validate key format
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        default_value = prompt_service.get_default(key)

        # Clear override
        prompt_service.clear_override(key)

        return PromptUpdateResponse(
            key=key,
            current_value=default_value or "",
            has_override=False,
        )


@router.post(
    "/prompts/{key:path}/test",
    response_model=PromptTestResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def test_prompt(key: str, request: PromptTestRequest) -> PromptTestResponse:
    """Test a prompt template by rendering it with variables.

    Renders the prompt template (or a draft value) with the provided
    variables, returning the rendered result. Variables not provided
    are left as {placeholder} in the output.
    """
    with get_db() as db:
        prompt_service = PromptService(db)

        # Validate key format
        parts = key.split(".")
        if len(parts) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt key format: {key}. Expected: category.name.prompt_type",
            )

        # Get the template to render
        if request.draft_value is not None:
            template = request.draft_value
        else:
            template = prompt_service.get_prompt(key)
            if not template:
                raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        # Extract variable names from template
        variable_names = _extract_variable_names(template)

        # Render with provided variables
        rendered = prompt_service.render_template(template, request.variables)

        return PromptTestResponse(
            rendered_prompt=rendered,
            variable_names=variable_names,
        )


def _extract_variable_names(template: str) -> list[str]:
    """Extract {variable} names from a template string.

    Handles doubled braces ({{ }}) by skipping them.
    """
    import re

    # Find all {name} patterns, excluding {{ (escaped braces)
    # This regex matches single braces only
    names: list[str] = []
    for match in re.finditer(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})", template):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names
