"""Tests for persona loader — YAML loading with default inheritance."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.agents.persona.loader import PersonaLoader
from src.agents.persona.models import PersonaConfig


# ---------------------------------------------------------------------------
# Fixtures: mock YAML data
# ---------------------------------------------------------------------------

_DEFAULT_YAML = {
    "name": "Default Analyst",
    "role": "Balanced analyst",
    "domain_focus": {
        "primary": ["ai", "ml"],
        "secondary": ["devops"],
    },
    "analysis_preferences": {
        "depth": "thorough",
        "perspective": "both",
        "time_horizon": "6_months",
        "novelty_bias": 0.5,
    },
    "relevance_weighting": {
        "strategic_impact": 0.3,
        "technical_depth": 0.25,
        "novelty": 0.25,
        "cross_domain_relevance": 0.2,
    },
    "model_overrides": {},
    "approval_overrides": {},
    "restricted_tools": [],
    "output_defaults": {
        "default_format": "digest",
        "include_code_examples": False,
        "include_architecture_diagrams": False,
        "include_confidence": True,
        "include_sources": True,
        "max_insight_length": 500,
    },
    "communication_style": {
        "tone": "professional_concise",
        "format": "structured_markdown",
        "audience": "technical_leaders",
    },
}

_TECH_YAML = {
    "name": "Tech Analyst",
    "role": "ML engineer",
    "domain_focus": {
        "primary": ["deep_learning", "nlp"],
    },
    "analysis_preferences": {
        "depth": "exhaustive",
        "novelty_bias": 0.8,
    },
    "model_overrides": {
        "theme_analysis": "claude-sonnet-4-5",
    },
    "output_defaults": {
        "default_format": "technical_report",
        "include_code_examples": True,
    },
}


def _mock_read_yaml(name: str) -> dict:
    """Return mock YAML data by persona name."""
    if name == "default":
        return _DEFAULT_YAML.copy()
    if name == "tech":
        return _TECH_YAML.copy()
    raise FileNotFoundError(f"Persona file not found: settings/personas/{name}.yaml")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPersonaLoaderLoad:
    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_load_default(self, mock_read: object) -> None:
        persona = PersonaLoader.load("default")
        assert isinstance(persona, PersonaConfig)
        assert persona.name == "Default Analyst"
        assert persona.domain_focus.primary == ["ai", "ml"]

    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_load_named_persona_inherits_defaults(self, mock_read: object) -> None:
        persona = PersonaLoader.load("tech")
        assert persona.name == "Tech Analyst"  # Overridden
        assert persona.role == "ML engineer"  # Overridden
        # domain_focus.primary overridden, secondary inherited from default
        assert persona.domain_focus.primary == ["deep_learning", "nlp"]
        assert persona.domain_focus.secondary == ["devops"]

    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_deep_merge_nested_fields(self, mock_read: object) -> None:
        persona = PersonaLoader.load("tech")
        # analysis_preferences: depth overridden, perspective inherited
        assert persona.analysis_preferences.depth == "exhaustive"
        assert persona.analysis_preferences.perspective == "both"
        assert persona.analysis_preferences.novelty_bias == 0.8

    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_model_overrides_from_persona(self, mock_read: object) -> None:
        persona = PersonaLoader.load("tech")
        assert persona.model_overrides == {"theme_analysis": "claude-sonnet-4-5"}

    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_output_defaults_merge(self, mock_read: object) -> None:
        persona = PersonaLoader.load("tech")
        assert persona.output_defaults.default_format == "technical_report"
        assert persona.output_defaults.include_code_examples is True
        # Inherited from default
        assert persona.output_defaults.include_confidence is True
        assert persona.output_defaults.max_insight_length == 500

    @patch.object(PersonaLoader, "_read_yaml", side_effect=_mock_read_yaml)
    def test_missing_persona_raises_file_not_found(self, mock_read: object) -> None:
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            PersonaLoader.load("nonexistent")


class TestPersonaLoaderListPersonas:
    @patch.object(Path, "is_dir", return_value=True)
    @patch.object(Path, "glob")
    def test_lists_yaml_files(self, mock_glob: object, mock_is_dir: object) -> None:
        mock_file_1 = Path("settings/personas/default.yaml")
        mock_file_2 = Path("settings/personas/tech.yaml")
        # Patch is_file on the individual Path objects
        with patch.object(Path, "is_file", return_value=True):
            mock_glob.return_value = [mock_file_1, mock_file_2]
            result = PersonaLoader.list_personas()
        assert result == ["default", "tech"]

    @patch.object(Path, "is_dir", return_value=False)
    def test_returns_empty_when_dir_missing(self, mock_is_dir: object) -> None:
        result = PersonaLoader.list_personas()
        assert result == []


class TestDeepMerge:
    def test_scalar_override(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = PersonaLoader._deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_dict_merge(self) -> None:
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = PersonaLoader._deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_list_replacement_not_merge(self) -> None:
        base = {"tags": [1, 2, 3]}
        override = {"tags": [4, 5]}
        result = PersonaLoader._deep_merge(base, override)
        assert result == {"tags": [4, 5]}

    def test_does_not_mutate_inputs(self) -> None:
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        PersonaLoader._deep_merge(base, override)
        assert base == {"a": {"x": 1}}
        assert override == {"a": {"y": 2}}

    def test_empty_override(self) -> None:
        base = {"a": 1}
        result = PersonaLoader._deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self) -> None:
        result = PersonaLoader._deep_merge({}, {"a": 1})
        assert result == {"a": 1}
