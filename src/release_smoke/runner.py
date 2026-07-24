"""Read-only API and CLI release-smoke adapters."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from src.release_smoke.models import ProtectedTargetPolicy, SurfaceObservation

_TRUSTED_API_SOURCES = frozenset({"railway_commit_sha", "github_sha"})


class ReleaseSmokeError(RuntimeError):
    """A release-smoke check failed without exposing raw response content."""


def _require_success(response: httpx.Response, check: str) -> None:
    if response.is_redirect:
        raise ReleaseSmokeError(f"{check} returned a redirect")
    if response.status_code != 200:
        raise ReleaseSmokeError(f"{check} returned HTTP {response.status_code}")


def _json_object(response: httpx.Response, check: str) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError as exc:
        raise ReleaseSmokeError(f"{check} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReleaseSmokeError(f"{check} returned a non-object document")
    return value


def run_api_discovery(
    policy: ProtectedTargetPolicy,
    *,
    admin_key: str,
    transport: httpx.BaseTransport | None = None,
) -> SurfaceObservation:
    """Observe API identity and canonical first-page discovery."""
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        timeout=20.0,
    ) as client:
        health = client.get(f"{policy.api_origin}/health")
        _require_success(health, "API health")
        health_document = _json_object(health, "API health")
        try:
            observation = SurfaceObservation.model_validate(
                {
                    "revision": health_document.get("revision"),
                    "revision_source": health_document.get("revision_source"),
                }
            )
        except ValidationError as exc:
            raise ReleaseSmokeError("API health returned invalid release identity") from exc
        if policy.target != "local":
            if observation.revision_source not in _TRUSTED_API_SOURCES:
                raise ReleaseSmokeError("API release identity has untrusted provenance")
            if observation.revision != policy.expected_api_revision:
                raise ReleaseSmokeError("API release revision does not match protected policy")

        headers = {"X-Admin-Key": admin_key}
        for path in ("/api/v1/capabilities", "/api/v1/configured-sources"):
            response = client.get(
                f"{policy.api_origin}{path}",
                params={"limit": 100},
                headers=headers,
            )
            _require_success(response, f"API discovery {path}")
            _json_object(response, f"API discovery {path}")
            if "cursor" in response.request.url.params:
                raise ReleaseSmokeError("First discovery page serialized cursor")
    return observation


def build_cli_environment(
    policy: ProtectedTargetPolicy,
    admin_key: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a minimal environment for the trusted installed CLI."""
    source = os.environ if environ is None else environ
    environment = {
        key: source[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT") if key in source
    }
    environment.update(
        {
            "API_BASE_URL": policy.api_origin,
            "ADMIN_API_KEY": admin_key,
            "ENVIRONMENT": "production" if policy.target != "local" else "development",
        }
    )
    return environment


def _resolve_command(command: Sequence[str] | None) -> list[str]:
    requested = list(command or ("aca",))
    if not requested:
        raise ReleaseSmokeError("CLI command is empty")
    executable = shutil.which(requested[0])
    if executable is None:
        raise ReleaseSmokeError("aca executable is unavailable")
    return [executable, *requested[1:]]


def run_cli_discovery(
    policy: ProtectedTargetPolicy,
    *,
    admin_key: str,
    command: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Execute canonical discovery through a real CLI subprocess."""
    base_command = _resolve_command(command)
    environment = build_cli_environment(policy, admin_key, environ=environ)
    with tempfile.TemporaryDirectory(prefix="aca-release-smoke-") as working_directory:
        for subcommand in ("capabilities", "configured-sources"):
            invocation = [*base_command, "--json", subcommand]
            result = subprocess.run(
                invocation,
                cwd=working_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise ReleaseSmokeError(f"CLI {subcommand} discovery failed")
            try:
                document = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise ReleaseSmokeError(f"CLI {subcommand} returned invalid JSON") from exc
            if not isinstance(document, dict):
                raise ReleaseSmokeError(f"CLI {subcommand} returned a non-object document")
