"""Notification preferences API routes.

Per-event-type notification preferences using the settings override system.
Keys follow the pattern `notification.<event_type>` with "true"/"false" values.
All event types default to enabled.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.models.notification import NotificationEventType
from src.services.settings_service import SettingsService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/settings/notifications", tags=["settings"])

# Event type descriptions for the UI
_EVENT_DESCRIPTIONS: dict[str, str] = {
    NotificationEventType.BATCH_SUMMARY: "Batch summarization completed",
    NotificationEventType.THEME_ANALYSIS: "Theme analysis completed",
    NotificationEventType.DIGEST_CREATION: "Daily or weekly digest created",
    NotificationEventType.SCRIPT_GENERATION: "Podcast script generated",
    NotificationEventType.AUDIO_GENERATION: "Audio digest or podcast generated",
    NotificationEventType.PIPELINE_COMPLETION: "Full pipeline run completed",
    NotificationEventType.JOB_FAILURE: "Background job failed",
}


# ============================================================================
# Response Models
# ============================================================================


class NotificationPreferenceInfo(BaseModel):
    """A single notification preference with value and source."""

    event_type: str
    description: str
    enabled: bool
    source: str  # "env" | "db" | "default"


class NotificationPreferencesResponse(BaseModel):
    """All notification preferences."""

    preferences: list[NotificationPreferenceInfo]


class NotificationPreferenceUpdate(BaseModel):
    """Request to update a notification preference."""

    enabled: bool


# ============================================================================
# Helpers
# ============================================================================


def _resolve_preference(event_type: str, service: SettingsService) -> tuple[bool, str]:
    """Resolve a notification preference and its source.

    Returns (enabled, source) where source is "env", "db", or "default".
    """
    env_var = f"NOTIFICATION_{event_type.upper()}"
    env_value = os.environ.get(env_var)
    if env_value is not None:
        return env_value.lower() == "true", "env"

    db_value = service.get(f"notification.{event_type}")
    if db_value is not None:
        return db_value.lower() == "true", "db"

    # Default: all enabled
    return True, "default"


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_notification_preferences() -> NotificationPreferencesResponse:
    """Get all notification preferences with source indicators."""
    with get_db() as db:
        service = SettingsService(db)

        preferences = []
        for event_type in NotificationEventType:
            enabled, source = _resolve_preference(event_type.value, service)
            preferences.append(
                NotificationPreferenceInfo(
                    event_type=event_type.value,
                    description=_EVENT_DESCRIPTIONS.get(event_type, ""),
                    enabled=enabled,
                    source=source,
                )
            )

        return NotificationPreferencesResponse(preferences=preferences)


@router.put(
    "/{event_type}",
    dependencies=[Depends(verify_admin_key)],
)
async def update_notification_preference(
    event_type: str,
    request: NotificationPreferenceUpdate,
) -> dict:
    """Update a notification preference for a specific event type."""
    # Validate event type
    valid_types = [e.value for e in NotificationEventType]
    if event_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {event_type}. Valid types: {valid_types}",
        )

    # Check if controlled by env var
    env_var = f"NOTIFICATION_{event_type.upper()}"
    if os.environ.get(env_var) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Preference '{event_type}' is controlled by environment variable "
            f"{env_var}. Remove the env var to allow DB overrides.",
        )

    with get_db() as db:
        service = SettingsService(db)
        service.set(f"notification.{event_type}", str(request.enabled).lower())
        return {
            "event_type": event_type,
            "enabled": request.enabled,
            "source": "db",
        }


@router.delete(
    "/{event_type}",
    dependencies=[Depends(verify_admin_key)],
)
async def reset_notification_preference(event_type: str) -> dict:
    """Reset a notification preference to its default (enabled)."""
    valid_types = [e.value for e in NotificationEventType]
    if event_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {event_type}. Valid types: {valid_types}",
        )

    with get_db() as db:
        service = SettingsService(db)
        service.delete(f"notification.{event_type}")
        return {
            "event_type": event_type,
            "enabled": True,
            "source": "default",
        }
