"""Typed target policy and release-smoke observation models."""

from __future__ import annotations

import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_TARGET_ID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")

TargetClass = Literal["production", "staging", "ephemeral", "local"]
RevisionSource = Literal[
    "railway_commit_sha",
    "github_sha",
    "verified_detached_sha",
    "local_development",
]


def normalize_origin(value: str) -> str:
    """Return a scheme/host/port origin or reject any broader URL."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Expected an HTTP(S) origin without credentials, path, query, or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Origin has an invalid port") from exc
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{parsed.scheme}://{host}{f':{port}' if port is not None else ''}"


def _is_loopback(origin: str) -> bool:
    hostname = urlsplit(origin).hostname
    if hostname == "localhost":
        return True
    try:
        return hostname is not None and ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class ProtectedTargetPolicy(BaseModel):
    """Exact environment policy loaded from approval-protected configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    target: TargetClass
    frontend_origin: str
    api_origin: str
    expected_frontend_revision: str | None
    expected_api_revision: str | None
    production_origins: list[str] = Field(max_length=16)

    @field_validator("target_id")
    @classmethod
    def validate_target_id(cls, value: str) -> str:
        if not _TARGET_ID.fullmatch(value):
            raise ValueError("Target ID must be a stable lowercase opaque identifier")
        return value

    @field_validator("frontend_origin", "api_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        return normalize_origin(value)

    @field_validator("production_origins")
    @classmethod
    def validate_production_origins(cls, values: list[str]) -> list[str]:
        normalized = [normalize_origin(value) for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Production origins must be unique")
        return normalized

    @field_validator("expected_frontend_revision", "expected_api_revision")
    @classmethod
    def validate_revision(cls, value: str | None) -> str | None:
        if value is not None and not _COMMIT_SHA.fullmatch(value):
            raise ValueError("Expected revision must be a lowercase 40-character commit SHA")
        return value

    @model_validator(mode="after")
    def validate_target_boundary(self) -> ProtectedTargetPolicy:
        origins = {self.frontend_origin, self.api_origin}
        if self.target == "local":
            if not all(_is_loopback(origin) for origin in origins):
                raise ValueError("Local targets must use loopback origins")
        else:
            if not all(origin.startswith("https://") for origin in origins):
                raise ValueError("Non-local targets must use HTTPS")
            if self.expected_frontend_revision is None or self.expected_api_revision is None:
                raise ValueError("Release targets require both expected revisions")
        if self.target in {"staging", "ephemeral"} and origins.intersection(
            self.production_origins
        ):
            raise ValueError("Non-production target resolves to a production origin")
        return self


class SurfaceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    revision: str
    revision_source: RevisionSource
