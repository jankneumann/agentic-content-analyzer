"""
Voice Configuration API Routes

Endpoints for configuring TTS provider, voice, speed, and presets
for audio digests and podcasts.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.config.settings import AUDIO_DIGEST_VOICE_PRESETS
from src.services.settings_service import SettingsService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/settings/voice", tags=["settings"])

VALID_PROVIDERS = ["openai", "elevenlabs"]
SPEED_MIN = 0.5
SPEED_MAX = 2.0


# ============================================================================
# Response Models
# ============================================================================


class VoicePreset(BaseModel):
    """A voice preset with provider-specific voice IDs."""

    name: str
    voices: dict[str, str]  # provider -> voice_id


class VoiceSettingInfo(BaseModel):
    """A single voice setting with value and source."""

    key: str
    value: str
    source: str  # "env" | "db" | "default"


class VoiceSettingsResponse(BaseModel):
    """Full voice configuration."""

    provider: VoiceSettingInfo
    default_voice: VoiceSettingInfo
    speed: VoiceSettingInfo
    presets: list[VoicePreset]
    valid_providers: list[str]


class VoiceUpdateRequest(BaseModel):
    """Request to update a voice setting."""

    value: str = Field(..., min_length=1)


# ============================================================================
# Helpers
# ============================================================================

# Mapping of voice setting keys to env vars and Settings field defaults
_VOICE_SETTINGS = {
    "provider": {
        "env_var": "AUDIO_DIGEST_PROVIDER",
        "settings_field": "audio_digest_provider",
        "default": "openai",
    },
    "default_voice": {
        "env_var": "AUDIO_DIGEST_DEFAULT_VOICE",
        "settings_field": "audio_digest_default_voice",
        "default": "nova",
    },
    "speed": {
        "env_var": "AUDIO_DIGEST_SPEED",
        "settings_field": "audio_digest_speed",
        "default": "1.0",
    },
}


def _resolve_voice_setting(field: str, service: SettingsService) -> tuple[str, str]:
    """Resolve a voice setting value and source.

    Returns (value, source) where source is "env", "db", or "default".
    """
    config = _VOICE_SETTINGS[field]
    env_value = os.environ.get(config["env_var"])
    if env_value:
        return env_value, "env"

    db_value = service.get(f"voice.{field}")
    if db_value:
        return db_value, "db"

    return str(config["default"]), "default"


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=VoiceSettingsResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_voice_settings() -> VoiceSettingsResponse:
    """Get current voice configuration with source indicators."""
    with get_db() as db:
        service = SettingsService(db)

        provider_val, provider_src = _resolve_voice_setting("provider", service)
        voice_val, voice_src = _resolve_voice_setting("default_voice", service)
        speed_val, speed_src = _resolve_voice_setting("speed", service)

        presets = [
            VoicePreset(name=name, voices=voices)
            for name, voices in AUDIO_DIGEST_VOICE_PRESETS.items()
        ]

        return VoiceSettingsResponse(
            provider=VoiceSettingInfo(
                key="voice.provider", value=provider_val, source=provider_src
            ),
            default_voice=VoiceSettingInfo(
                key="voice.default_voice", value=voice_val, source=voice_src
            ),
            speed=VoiceSettingInfo(key="voice.speed", value=speed_val, source=speed_src),
            presets=presets,
            valid_providers=VALID_PROVIDERS,
        )


@router.put(
    "/{field}",
    dependencies=[Depends(verify_admin_key)],
)
async def update_voice_setting(field: str, request: VoiceUpdateRequest) -> dict:
    """Update a voice configuration setting.

    Valid fields: provider, default_voice, speed
    """
    if field not in _VOICE_SETTINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice setting: {field}. Valid fields: {list(_VOICE_SETTINGS.keys())}",
        )

    # Check if controlled by env var
    config = _VOICE_SETTINGS[field]
    if os.environ.get(config["env_var"]):
        raise HTTPException(
            status_code=409,
            detail=f"Setting '{field}' is controlled by environment variable "
            f"{config['env_var']}. Remove the env var to allow DB overrides.",
        )

    # Validate specific fields
    if field == "provider" and request.value not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {request.value}. Valid providers: {VALID_PROVIDERS}",
        )

    if field == "speed":
        try:
            speed = float(request.value)
            if speed < SPEED_MIN or speed > SPEED_MAX:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid speed: {request.value}. "
                f"Must be a number between {SPEED_MIN} and {SPEED_MAX}.",
            )

    with get_db() as db:
        service = SettingsService(db)
        service.set(f"voice.{field}", request.value)
        return {"field": field, "value": request.value, "source": "db"}


@router.delete(
    "/{field}",
    dependencies=[Depends(verify_admin_key)],
)
async def reset_voice_setting(field: str) -> dict:
    """Reset a voice setting to its default."""
    if field not in _VOICE_SETTINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice setting: {field}. Valid fields: {list(_VOICE_SETTINGS.keys())}",
        )

    with get_db() as db:
        service = SettingsService(db)
        service.delete(f"voice.{field}")
        return {
            "field": field,
            "value": _VOICE_SETTINGS[field]["default"],
            "source": "default",
        }
