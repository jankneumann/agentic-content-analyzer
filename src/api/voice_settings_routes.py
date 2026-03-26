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
    input_language: VoiceSettingInfo
    input_continuous: VoiceSettingInfo
    input_auto_submit: VoiceSettingInfo
    cloud_stt_language: VoiceSettingInfo
    engine_preference_order: VoiceSettingInfo
    stt_model_size: VoiceSettingInfo
    cloud_stt_model: str  # Read-only: current CLOUD_STT pipeline step model
    presets: list[VoicePreset]
    valid_providers: list[str]
    valid_input_languages: list[str]
    valid_cloud_stt_languages: list[str]
    valid_engine_names: list[str]
    valid_stt_model_sizes: list[str]


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
    "input_language": {
        "env_var": "VOICE_INPUT_LANGUAGE",
        "settings_field": "voice_input_language",
        "default": "en-US",
    },
    "input_continuous": {
        "env_var": "VOICE_INPUT_CONTINUOUS",
        "settings_field": "voice_input_continuous",
        "default": "false",
    },
    "input_auto_submit": {
        "env_var": "VOICE_INPUT_AUTO_SUBMIT",
        "settings_field": "voice_input_auto_submit",
        "default": "false",
    },
    "cloud_stt_language": {
        "env_var": "CLOUD_STT_LANGUAGE",
        "settings_field": "cloud_stt_language",
        "default": "auto",
    },
    "engine_preference_order": {
        "env_var": "ENGINE_PREFERENCE_ORDER",
        "settings_field": "engine_preference_order",
        "default": "cloud,native,browser,on-device",
    },
    "stt_model_size": {
        "env_var": "STT_MODEL_SIZE",
        "settings_field": "stt_model_size",
        "default": "tiny",
    },
}

# Valid BCP-47 language tags for voice input
VALID_INPUT_LANGUAGES = [
    "en-US",
    "en-GB",
    "es-ES",
    "fr-FR",
    "de-DE",
    "ja-JP",
    "zh-CN",
]

VALID_BOOLEANS = ["true", "false"]

# Valid cloud STT language values (includes "auto" for auto-detection)
VALID_CLOUD_STT_LANGUAGES = [
    "auto",
    "en-US",
    "en-GB",
    "es-ES",
    "fr-FR",
    "de-DE",
    "ja-JP",
    "zh-CN",
]

# Valid engine names for preference order
VALID_ENGINE_NAMES = ["cloud", "native", "browser", "on-device"]

# Valid on-device STT model sizes
VALID_STT_MODEL_SIZES = ["tiny", "base"]


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
        lang_val, lang_src = _resolve_voice_setting("input_language", service)
        cont_val, cont_src = _resolve_voice_setting("input_continuous", service)
        auto_val, auto_src = _resolve_voice_setting("input_auto_submit", service)
        cloud_lang_val, cloud_lang_src = _resolve_voice_setting("cloud_stt_language", service)
        engine_val, engine_src = _resolve_voice_setting("engine_preference_order", service)
        stt_size_val, stt_size_src = _resolve_voice_setting("stt_model_size", service)

        # Resolve current CLOUD_STT model (read-only)
        try:
            from src.config.models import ModelStep, get_model_config

            config = get_model_config()
            cloud_stt_model = config.get_model_for_step(ModelStep.CLOUD_STT)
        except Exception:
            cloud_stt_model = "unknown"

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
            input_language=VoiceSettingInfo(
                key="voice.input_language", value=lang_val, source=lang_src
            ),
            input_continuous=VoiceSettingInfo(
                key="voice.input_continuous", value=cont_val, source=cont_src
            ),
            input_auto_submit=VoiceSettingInfo(
                key="voice.input_auto_submit", value=auto_val, source=auto_src
            ),
            cloud_stt_language=VoiceSettingInfo(
                key="voice.cloud_stt_language", value=cloud_lang_val, source=cloud_lang_src
            ),
            engine_preference_order=VoiceSettingInfo(
                key="voice.engine_preference_order", value=engine_val, source=engine_src
            ),
            stt_model_size=VoiceSettingInfo(
                key="voice.stt_model_size", value=stt_size_val, source=stt_size_src
            ),
            cloud_stt_model=cloud_stt_model,
            presets=presets,
            valid_providers=VALID_PROVIDERS,
            valid_input_languages=VALID_INPUT_LANGUAGES,
            valid_cloud_stt_languages=VALID_CLOUD_STT_LANGUAGES,
            valid_engine_names=VALID_ENGINE_NAMES,
            valid_stt_model_sizes=VALID_STT_MODEL_SIZES,
        )


@router.put(
    "/{field}",
    dependencies=[Depends(verify_admin_key)],
)
async def update_voice_setting(field: str, request: VoiceUpdateRequest) -> dict:
    """Update a voice configuration setting.

    Valid fields: provider, default_voice, speed, input_language,
    input_continuous, input_auto_submit
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

    if field == "input_language" and request.value not in VALID_INPUT_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {request.value}. Valid languages: {VALID_INPUT_LANGUAGES}",
        )

    if field in ("input_continuous", "input_auto_submit") and request.value not in VALID_BOOLEANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value for {field}: {request.value}. Must be 'true' or 'false'.",
        )

    if field == "cloud_stt_language" and request.value not in VALID_CLOUD_STT_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cloud STT language: {request.value}. "
            f"Valid languages: {VALID_CLOUD_STT_LANGUAGES}",
        )

    if field == "engine_preference_order":
        engines = [e.strip() for e in request.value.split(",")]
        invalid = [e for e in engines if e not in VALID_ENGINE_NAMES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid engine names: {invalid}. Valid engines: {VALID_ENGINE_NAMES}",
            )

    if field == "stt_model_size" and request.value not in VALID_STT_MODEL_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid STT model size: {request.value}. Valid sizes: {VALID_STT_MODEL_SIZES}",
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
