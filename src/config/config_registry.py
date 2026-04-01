"""ConfigRegistry — centralized YAML-based configuration default loading.

Provides a unified interface for loading, caching, and accessing YAML-based
configuration defaults across all settings domains (prompts, models, voice,
notifications). Domain-specific logic (template rendering, DB overrides)
remains in the respective services — this registry only handles YAML loading.

Design decisions: D1, D2, D3 (see openspec/changes/settings-reorganization/design.md)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ConfigDomain:
    """Registration descriptor for a settings domain."""

    name: str
    yaml_file: str
    key_separator: str = "."


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent.parent  # fallback: src/config -> project root


class ConfigRegistry:
    """Manages YAML-based configuration defaults for all settings domains.

    Usage::

        registry = ConfigRegistry()
        registry.register(ConfigDomain(name="prompts", yaml_file="prompts.yaml"))
        value = registry.get("prompts", "chat.summary.system")
        keys = registry.list_keys("prompts")
        registry.reload("prompts")
    """

    def __init__(self, settings_dir: Path | None = None) -> None:
        if settings_dir is None:
            settings_dir = _find_project_root() / "settings"
        self._settings_dir = settings_dir
        self._domains: dict[str, ConfigDomain] = {}
        self._cache: dict[str, dict] = {}

    def register(self, domain: ConfigDomain) -> None:
        """Register a settings domain for lazy loading.

        Raises ValueError if a domain with the same name is already registered.
        """
        if domain.name in self._domains:
            raise ValueError(
                f"Domain '{domain.name}' is already registered. "
                f"Registered domains: {list(self._domains.keys())}"
            )
        self._domains[domain.name] = domain

    def get(self, domain: str, key: str) -> Any:
        """Get a default value from a domain's YAML by dot-separated key path.

        Returns None if the key doesn't exist or resolves to a null YAML value.
        Raises ValueError for unregistered domains.
        Raises FileNotFoundError if the YAML file doesn't exist.
        Raises yaml.YAMLError if the YAML file has invalid syntax.
        """
        self._ensure_loaded(domain)
        return self._resolve_key(domain, key)

    def get_raw(self, domain: str) -> dict:
        """Get the entire parsed YAML dict for a domain.

        Useful for services that need to walk the full tree (e.g., PromptService.list_all_prompts).
        """
        self._ensure_loaded(domain)
        return self._cache[domain]

    def list_keys(self, domain: str) -> list[str]:
        """List all leaf-node keys in a domain as dot-separated paths.

        Intermediate dict nodes are not included — only paths to scalar/list values.
        """
        self._ensure_loaded(domain)
        data = self._cache[domain]
        sep = self._domains[domain].key_separator
        keys: list[str] = []
        self._collect_leaf_keys(data, "", sep, keys)
        return keys

    def reload(self, domain: str) -> None:
        """Reload a domain's YAML from disk, invalidating the cache."""
        self._validate_domain(domain)
        if domain in self._cache:
            del self._cache[domain]
        self._load(domain)

    def reload_all(self) -> None:
        """Reload all registered domains from disk."""
        self._cache.clear()
        for domain_name in self._domains:
            self._load(domain_name)

    @property
    def registered_domains(self) -> list[str]:
        """List names of all registered domains."""
        return list(self._domains.keys())

    def _ensure_loaded(self, domain: str) -> None:
        self._validate_domain(domain)
        if domain not in self._cache:
            self._load(domain)

    def _validate_domain(self, domain: str) -> None:
        if domain not in self._domains:
            raise ValueError(
                f"Domain '{domain}' is not registered. "
                f"Available domains: {list(self._domains.keys())}"
            )

    def _load(self, domain: str) -> None:
        config = self._domains[domain]
        yaml_path = self._settings_dir / config.yaml_file
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Settings YAML file not found: {yaml_path} (domain: '{domain}')"
            )
        with open(yaml_path) as f:
            self._cache[domain] = yaml.safe_load(f) or {}

    def _resolve_key(self, domain: str, key: str) -> Any:
        data = self._cache[domain]
        sep = self._domains[domain].key_separator
        parts = key.split(sep)
        current: Any = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    def _collect_leaf_keys(self, data: dict, prefix: str, sep: str, result: list[str]) -> None:
        for k, v in data.items():
            full_key = f"{prefix}{sep}{k}" if prefix else k
            if isinstance(v, dict) and v:
                self._collect_leaf_keys(v, full_key, sep, result)
            else:
                result.append(full_key)


# Module-level singleton — initialized at import, domains registered at startup
_registry: ConfigRegistry | None = None


def get_config_registry() -> ConfigRegistry:
    """Get the global ConfigRegistry singleton.

    Creates the instance on first call. Domains are registered separately
    via ``register_all_domains()``.
    """
    global _registry
    if _registry is None:
        _registry = ConfigRegistry()
    return _registry


def register_all_domains(registry: ConfigRegistry | None = None) -> ConfigRegistry:
    """Register all standard settings domains.

    Called during FastAPI lifespan or module initialization.
    """
    if registry is None:
        registry = get_config_registry()

    domains = [
        ConfigDomain(name="prompts", yaml_file="prompts.yaml"),
        ConfigDomain(name="models", yaml_file="models.yaml"),
        ConfigDomain(name="voice", yaml_file="voice.yaml"),
        ConfigDomain(name="notifications", yaml_file="notifications.yaml"),
    ]

    for domain in domains:
        if domain.name not in registry.registered_domains:
            registry.register(domain)

    # Eagerly validate all YAML files are loadable at startup
    for domain in domains:
        registry.get_raw(domain.name)  # Forces load, raises on missing/invalid YAML

    return registry


def reset_registry() -> None:
    """Reset the global registry singleton. For testing only."""
    global _registry
    _registry = None
