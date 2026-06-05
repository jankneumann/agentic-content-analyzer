"""Load and validate the Railway secret-sync allowlist mapping.

``settings/deploy/railway_secrets.yaml`` declares, per Railway service, which
local secret keys may be pushed and under what Railway variable name. This is
the ONLY source of eligibility — a key absent from this file is never synced to
Railway. That allowlist is the core guardrail that prevents local-only dev
values (e.g. a localhost ``database_url``) from leaking into a deployed service.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

DEFAULT_MAPPING_FILE = Path("settings/deploy/railway_secrets.yaml")


class DeploySecretsError(Exception):
    """Raised when the mapping file is missing or malformed."""


@dataclass(frozen=True)
class SecretMapping:
    """One eligible secret: its local key and its Railway variable name."""

    local: str
    railway: str  # Railway variable name (defaults to ``local`` when unspecified)


@dataclass(frozen=True)
class ServiceMapping:
    """The resolved set of eligible secrets for one Railway service."""

    service: str
    secrets: tuple[SecretMapping, ...]


def _coerce_entry(raw: object, service: str) -> SecretMapping:
    """Normalize a single ``secrets`` list entry into a ``SecretMapping``."""
    if isinstance(raw, str):
        return SecretMapping(local=raw, railway=raw)
    if isinstance(raw, dict):
        local = raw.get("local")
        if not isinstance(local, str) or not local:
            raise DeploySecretsError(
                f"service '{service}': each secret entry needs a non-empty string 'local'"
            )
        railway = raw.get("railway", local)
        if not isinstance(railway, str) or not railway:
            raise DeploySecretsError(
                f"service '{service}': 'railway' for '{local}' must be a non-empty string"
            )
        return SecretMapping(local=local, railway=railway)
    raise DeploySecretsError(
        f"service '{service}': secret entries must be a string or mapping, got {type(raw).__name__}"
    )


def load_mapping(path: Path | None = None) -> dict[str, ServiceMapping]:
    """Return ``{service_name: ServiceMapping}`` from the mapping file.

    Resolves ``extends`` (a service may inherit another's secret list), validates
    the shape, and rejects duplicate Railway target names within a service.

    Raises:
        DeploySecretsError: if the file is missing, not valid YAML, structurally
            wrong, references an unknown ``extends`` parent, has a cycle, or maps
            two local keys to the same Railway variable name.
    """
    path = path or DEFAULT_MAPPING_FILE
    if not Path(path).exists():
        raise DeploySecretsError(f"mapping file not found: {path}")

    try:
        data = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as e:
        raise DeploySecretsError(f"invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict) or "services" not in data:
        raise DeploySecretsError("mapping must have a top-level 'services' key")
    services_raw = data["services"]
    if not isinstance(services_raw, dict):
        raise DeploySecretsError("'services' must be a mapping of service-name -> config")

    own: dict[str, list[SecretMapping]] = {}
    extends: dict[str, str] = {}
    for name, cfg in services_raw.items():
        if not isinstance(cfg, dict):
            raise DeploySecretsError(f"service '{name}' must be a mapping")
        entries = cfg.get("secrets", []) or []
        if not isinstance(entries, list):
            raise DeploySecretsError(f"service '{name}': 'secrets' must be a list")
        own[name] = [_coerce_entry(e, name) for e in entries]
        if "extends" in cfg:
            parent = cfg["extends"]
            if parent not in services_raw:
                raise DeploySecretsError(f"service '{name}' extends unknown service '{parent}'")
            extends[str(name)] = str(parent)

    def _resolve(name: str, seen: frozenset[str]) -> list[SecretMapping]:
        if name in seen:
            raise DeploySecretsError(f"circular 'extends' involving service '{name}'")
        seen = seen | {name}
        merged: list[SecretMapping] = []
        if name in extends:
            merged.extend(_resolve(extends[name], seen))
        merged.extend(own[name])
        return merged

    services: dict[str, ServiceMapping] = {}
    for name in services_raw:
        merged = _resolve(str(name), frozenset())
        targets = [s.railway for s in merged]
        dupes = sorted({t for t in targets if targets.count(t) > 1})
        if dupes:
            raise DeploySecretsError(f"service '{name}': duplicate Railway target name(s): {dupes}")
        services[str(name)] = ServiceMapping(service=str(name), secrets=tuple(merged))
    return services
