"""Source override write API routes.

Admin-authenticated endpoints to add/update, delete, and enable/disable
database-backed ingestion source overrides. These merge on top of the
sources.d/ YAML defaults via load_sources_config(). Read access (overview with
origin) lives in source_routes.py.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.services.source_override_service import (
    PublicSourceKeyError,
    SourceOverrideError,
    SourceOverrideService,
    public_source_key,
)
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Shares the /api/v1/sources prefix with the read-only overview router.
router = APIRouter(prefix="/api/v1/sources", tags=["sources"])

SourceKey = Annotated[str, Path(min_length=1, pattern=r"^[^\x00]+$")]


# ============================================================================
# Request / Response Models
# ============================================================================


class SourceUpsertRequest(BaseModel):
    """Add or update a source override. The config is the full source dict."""

    config: dict[str, Any] = Field(
        description="Full source definition, validated against the Source union "
        "(must include a 'type' field and the type's required fields)."
    )
    description: str | None = Field(default=None, description="Optional human note")


class SourceEnabledRequest(BaseModel):
    """Enable or disable a source by key."""

    enabled: bool


class SourceMutationResult(BaseModel):
    source_key: str
    version: int
    origin: str = "db"
    enabled: bool


# ============================================================================
# Helpers
# ============================================================================


def _resolve_source_config(key: str) -> dict[str, Any] | None:
    """Return the resolved (merged) config for a source key, or None.

    Used as the fallback config when enabling/disabling a YAML-defined source
    that has no override row yet, so a self-describing shadow row can be created.
    """
    from src.config import settings
    from src.config.sources import configured_source_public_key, source_key as derive_source_key

    config = settings.get_sources_config()
    for source in config.sources:
        try:
            candidate_key = derive_source_key(source)
            if source.type == "obsidian_vault":
                candidate_key = configured_source_public_key(
                    source,
                    secret=settings.get_configured_source_key_secret(),
                )
            if candidate_key == key:
                data = source.model_dump()
                data.pop("origin", None)
                return data
        except ValueError:
            continue
    return None


# ============================================================================
# Endpoints
# ============================================================================


@router.post("", response_model=SourceMutationResult, dependencies=[Depends(verify_admin_key)])
async def upsert_source(request: SourceUpsertRequest) -> SourceMutationResult:
    """Add or update a source override (upsert by natural key).

    Validates the config against the Source union; returns 400 on invalid config.
    """
    with get_db() as db:
        service = SourceOverrideService(db)
        try:
            row = service.upsert(request.config, description=request.description)
        except SourceOverrideError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return SourceMutationResult(
            source_key=public_source_key(row), version=row.version, enabled=row.enabled
        )


@router.delete("/{key:path}", dependencies=[Depends(verify_admin_key)])
async def delete_source(key: SourceKey) -> dict:
    """Delete a source override (DB-origin) or remove a shadow (revert to YAML)."""
    with get_db() as db:
        service = SourceOverrideService(db)
        try:
            deleted_key = service.delete(key)
        except PublicSourceKeyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if deleted_key is None:
            raise HTTPException(status_code=404, detail=f"Source override not found: {key}")
        return {"source_key": deleted_key, "deleted": True}


@router.patch(
    "/{key:path}", response_model=SourceMutationResult, dependencies=[Depends(verify_admin_key)]
)
async def set_source_enabled(key: SourceKey, request: SourceEnabledRequest) -> SourceMutationResult:
    """Enable or disable a source.

    For a YAML-defined source with no override row, a self-describing shadow row
    is created from the resolved source config. Returns 404 if the key matches
    neither an override nor a YAML source.
    """
    with get_db() as db:
        service = SourceOverrideService(db)
        try:
            fallback = None if service.get(key) else _resolve_source_config(key)
            row = service.set_enabled(key, request.enabled, fallback_config=fallback)
        except PublicSourceKeyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SourceOverrideError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return SourceMutationResult(
            source_key=public_source_key(row), version=row.version, enabled=row.enabled
        )
