"""
Settings Override API Routes

Generic CRUD endpoints for the settings_overrides table.
Used by model, voice, and other settings domains.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.services.settings_service import SettingsService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/settings/overrides", tags=["settings"])

# Key format: namespace.name (e.g., "model.summarization", "voice.provider")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$")


# ============================================================================
# Request/Response Models
# ============================================================================


class SettingsOverrideInfo(BaseModel):
    """Information about a settings override."""

    key: str
    value: str
    version: int
    description: str | None = None


class SettingsOverrideListResponse(BaseModel):
    """Response containing settings overrides."""

    overrides: list[SettingsOverrideInfo]


class SettingsOverrideUpdateRequest(BaseModel):
    """Request to set a settings override."""

    value: str = Field(..., min_length=1, description="The override value")
    description: str | None = Field(None, description="Optional description of the change")


class SettingsOverrideUpdateResponse(BaseModel):
    """Response after setting an override."""

    key: str
    value: str
    version: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=SettingsOverrideListResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def list_overrides(prefix: str = "") -> SettingsOverrideListResponse:
    """List settings overrides, optionally filtered by key prefix.

    Query params:
        prefix: Filter keys by prefix (e.g., "model" returns all model.* keys)
    """
    with get_db() as db:
        service = SettingsService(db)
        overrides = service.list_by_prefix(prefix)
        return SettingsOverrideListResponse(
            overrides=[SettingsOverrideInfo(**o) for o in overrides]
        )


@router.get(
    "/{key:path}",
    response_model=SettingsOverrideInfo,
    dependencies=[Depends(verify_admin_key)],
)
async def get_override(key: str) -> SettingsOverrideInfo:
    """Get a specific settings override by key."""
    _validate_key(key)

    with get_db() as db:
        service = SettingsService(db)
        override = service.get_override(key)
        if not override:
            raise HTTPException(status_code=404, detail=f"Settings override not found: {key}")
        return SettingsOverrideInfo(
            key=override.key,
            value=override.value,
            version=override.version,
            description=override.description,
        )


@router.put(
    "/{key:path}",
    response_model=SettingsOverrideUpdateResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def set_override(
    key: str, request: SettingsOverrideUpdateRequest
) -> SettingsOverrideUpdateResponse:
    """Set a settings override value.

    Creates a new override or updates an existing one (with version increment).
    """
    _validate_key(key)

    with get_db() as db:
        service = SettingsService(db)
        service.set(key, request.value, description=request.description)
        override = service.get_override(key)
        return SettingsOverrideUpdateResponse(
            key=key,
            value=request.value,
            version=override.version if override else 1,
        )


@router.delete(
    "/{key:path}",
    dependencies=[Depends(verify_admin_key)],
)
async def delete_override(key: str) -> dict:
    """Delete a settings override, reverting to default behavior."""
    _validate_key(key)

    with get_db() as db:
        service = SettingsService(db)
        deleted = service.delete(key)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Settings override not found: {key}")
        return {"key": key, "deleted": True}


def _validate_key(key: str) -> None:
    """Validate settings key format (must be namespace.name pattern)."""
    if not KEY_PATTERN.match(key):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid settings key format: {key}. "
            "Must match pattern: namespace.name (e.g., 'model.summarization')",
        )
