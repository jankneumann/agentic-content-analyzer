"""Persona loader — reads YAML persona files with default inheritance.

Each persona YAML file in ``settings/personas/`` is a self-contained
agent profile. Missing sections inherit from ``default.yaml`` via
deep merge.
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from src.agents.persona.models import PersonaConfig

logger = logging.getLogger(__name__)


class PersonaLoader:
    """Loads persona YAML files from settings/personas/ with default inheritance."""

    PERSONAS_DIR = "settings/personas"

    @classmethod
    def load(cls, name: str = "default") -> PersonaConfig:
        """Load a persona by name.

        Missing fields inherit from ``default.yaml`` via deep merge.

        Args:
            name: Persona name (without ``.yaml`` extension).

        Returns:
            Validated PersonaConfig.

        Raises:
            FileNotFoundError: If the persona YAML file does not exist.
        """
        default_data = cls._read_yaml("default")

        if name == "default":
            return PersonaConfig(**default_data)

        persona_data = cls._read_yaml(name)
        merged = cls._deep_merge(default_data, persona_data)
        return PersonaConfig(**merged)

    @classmethod
    def list_personas(cls) -> list[str]:
        """List all available persona names (without .yaml extension)."""
        personas_dir = Path(cls.PERSONAS_DIR)
        if not personas_dir.is_dir():
            logger.warning("Personas directory not found: %s", cls.PERSONAS_DIR)
            return []
        return sorted(
            p.stem for p in personas_dir.glob("*.yaml") if p.is_file()
        )

    @classmethod
    def _read_yaml(cls, name: str) -> dict[str, Any]:
        """Read and parse a persona YAML file.

        Args:
            name: Persona name (without ``.yaml`` extension).

        Returns:
            Parsed YAML data as a dict.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
        """
        # Validate name to prevent path traversal (only alphanum, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(f"Invalid persona name: {name!r}")
        path = Path(cls.PERSONAS_DIR) / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Persona file not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override dict into base dict.

        - Dict values are merged recursively.
        - All other types (lists, scalars) in override replace the base value.
        - Keys in base that are absent from override are preserved.

        Returns:
            A new merged dict (neither input is mutated).
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = PersonaLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
