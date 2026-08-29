"""GX-10 production profile and activation policy."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.config.profiles import load_profile, validate_profile
from src.config.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "profiles" / "gx10.yaml"
SECRET_REFERENCE = re.compile(r"\$\{GX10_[A-Z0-9_]+(?::-[^}]*)?\}")


def _secret_environment() -> dict[str, str]:
    """Return unique non-production values for required external references."""

    return {
        "GX10_APP_DATABASE_URL": "postgresql://app-user:opaque@app-postgres:5432/newsletters",
        "GX10_APP_SECRET_KEY": "a" * 48,
        "GX10_CONFIGURED_SOURCE_KEY_SECRET": "b" * 48,
        "GX10_OPERATION_CURSOR_SIGNING_KEY": "c" * 48,
        "GX10_ADMIN_API_KEY": "d" * 48,
        "GX10_OPERATOR_API_KEY": "e" * 48,
        "GX10_PROXY_USERNAME": "aca-egress",
        "GX10_PROXY_PASSWORD": "f" * 48,
        "GX10_LANGFUSE_PUBLIC_KEY": "pk-lf-placeholder",
        "GX10_LANGFUSE_SECRET_KEY": "g" * 48,
        "GX10_NEO4J_PASSWORD": "h" * 48,
        "GX10_RELEASE_REVISION": "1" * 40,
        "GX10_AUTHORITY_FINGERPRINT": "2" * 64,
        "GX10_PROCESS_ROLE": "api",
        "OTEL_SERVICE_NAME": "aca-gx10-api",
        "TELEMETRY_SERVICE_INSTANCE_ID": "aca-gx10-api",
    }


def test_gx10_profile_declares_complete_local_observability_topology() -> None:
    profile = load_profile(
        "gx10",
        profiles_dir=ROOT / "profiles",
        env_vars=_secret_environment(),
        secrets={},
    )

    assert profile.settings.environment == "production"
    assert profile.providers.database == "local"
    assert profile.providers.graphdb == "neo4j"
    assert profile.providers.storage == "local"
    assert profile.providers.observability == "langfuse"
    assert validate_profile(profile, secrets={}, check_secrets=False) == []

    settings = profile.settings.model_dump(mode="json")
    assert settings["database"]["database_url"].split("@", 1)[1].startswith("app-postgres:")
    assert settings["neo4j"]["neo4j_uri"] == "bolt://neo4j:7687"
    assert settings["storage"]["storage_provider"] == "local"
    assert settings["observability"]["otel_exporter_otlp_endpoint"] == (
        "http://langfuse-web:3000/api/public/otel"
    )
    assert settings["observability"]["langfuse_base_url"] == "http://langfuse-web:3000"


def test_gx10_profile_uses_unique_process_identities_and_external_secret_references() -> None:
    raw = PROFILE_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    identities = data["settings"]["gx10"]["service_identities"]
    assert identities == {
        "api": "aca-gx10-api",
        "worker": "aca-gx10-worker",
        "scheduler": "aca-gx10-scheduler",
        "maintenance": "aca-gx10-maintenance",
    }
    assert len(set(identities.values())) == len(identities)

    required_refs = {
        "GX10_APP_DATABASE_URL",
        "GX10_APP_SECRET_KEY",
        "GX10_CONFIGURED_SOURCE_KEY_SECRET",
        "GX10_OPERATION_CURSOR_SIGNING_KEY",
        "GX10_ADMIN_API_KEY",
        "GX10_OPERATOR_API_KEY",
        "GX10_PROXY_USERNAME",
        "GX10_PROXY_PASSWORD",
        "GX10_LANGFUSE_PUBLIC_KEY",
        "GX10_LANGFUSE_SECRET_KEY",
        "GX10_NEO4J_PASSWORD",
        "GX10_RELEASE_REVISION",
        "GX10_AUTHORITY_FINGERPRINT",
    }
    actual_refs = {
        match.group(0)[2:].split(":-", 1)[0].rstrip("}") for match in SECRET_REFERENCE.finditer(raw)
    }
    assert required_refs <= actual_refs
    assert "operator_api_key:" in raw
    assert "proxy_password:" in raw
    assert "rotation_generation:" in raw


def test_gx10_profile_freezes_masking_sampling_retention_and_watermarks() -> None:
    data = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    observability = data["settings"]["observability"]
    gx10 = data["settings"]["gx10"]

    assert observability["observability_required"] is True
    assert observability["otel_enabled"] is True
    assert observability["otel_log_prompts"] is False
    assert observability["otel_traces_sampler_arg"] == 1.0
    assert observability["langfuse_sample_rate"] == 1.0
    assert gx10["masking_policy"] == "gx10-export-mask-v1"
    assert gx10["successful_trace_retention_days"] == 30
    assert gx10["failed_trace_retention_days"] == 90
    assert gx10["high_watermark_percent"] == 80
    assert gx10["high_clear_percent"] == 75
    assert gx10["critical_watermark_percent"] == 90
    assert gx10["critical_clear_percent"] == 85
    assert gx10["hysteresis_minutes"] == 15


def _valid_gx10_settings() -> dict[str, object]:
    return {
        "environment": "production",
        "configured_source_key_secret": "a" * 48,
        "gx10_runtime_enabled": True,
        "observability_provider": "langfuse",
        "observability_required": True,
        "otel_enabled": True,
        "otel_exporter_otlp_endpoint": "http://langfuse-web:3000/api/public/otel",
        "langfuse_public_key": "pk-lf-placeholder",
        "langfuse_secret_key": "b" * 48,
        "operator_api_key": "c" * 48,
        "gx10_process_role": "api",
        "otel_service_name": "aca-gx10-api",
        "telemetry_service_instance_id": "aca-gx10-api",
        "telemetry_release_revision": "1" * 40,
        "gx10_masking_policy": "gx10-export-mask-v1",
        "gx10_authority_fingerprint": "2" * 64,
        "gx10_proxy_username": "aca-egress",
        "gx10_proxy_password": "d" * 48,
    }


@pytest.mark.parametrize(
    "missing",
    [
        "otel_exporter_otlp_endpoint",
        "langfuse_public_key",
        "langfuse_secret_key",
        "operator_api_key",
        "telemetry_service_instance_id",
        "gx10_masking_policy",
        "gx10_authority_fingerprint",
        "gx10_proxy_username",
        "gx10_proxy_password",
    ],
)
def test_gx10_activation_rejects_incomplete_observability(missing: str) -> None:
    values = _valid_gx10_settings()
    values[missing] = None

    with pytest.raises(ValidationError, match=missing.upper()):
        Settings(_env_file=None, **values)


def test_gx10_activation_rejects_sampling_or_authority_drift() -> None:
    common = _valid_gx10_settings()

    with pytest.raises(ValidationError, match="sampling"):
        Settings(_env_file=None, langfuse_sample_rate=0.5, **common)
    with pytest.raises(ValidationError, match="GX10_AUTHORITY_FINGERPRINT"):
        Settings(
            _env_file=None,
            **{**common, "gx10_authority_fingerprint": "not-a-fingerprint"},
        )


def test_gx10_ownership_epoch_is_optional_and_bounded() -> None:
    common = _valid_gx10_settings()

    passive = Settings(_env_file=None, **common)
    assert passive.gx10_ownership_epoch is None

    active = Settings(_env_file=None, **{**common, "gx10_ownership_epoch": 17})
    assert active.gx10_ownership_epoch == 17

    with pytest.raises(ValidationError, match="gx10_ownership_epoch"):
        Settings(
            _env_file=None,
            **{**common, "gx10_ownership_epoch": -1},
        )
