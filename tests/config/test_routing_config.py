"""Tests for routing configuration loading.

Tests cover:
- YAML parsing of routing section
- Environment variable overrides (ROUTING_<STEP>_MODE)
- Default fallback (fixed mode, disabled)
- RoutingConfig dataclass defaults
- is_dynamic_routing_enabled logic
"""

import os

import pytest

from src.config.models import (
    ModelConfig,
    ModelStep,
    RoutingConfig,
    RoutingMode,
)


class TestRoutingMode:
    def test_fixed_value(self):
        assert RoutingMode.FIXED == "fixed"

    def test_dynamic_value(self):
        assert RoutingMode.DYNAMIC == "dynamic"


class TestRoutingConfig:
    def test_defaults(self):
        config = RoutingConfig(step="summarization")
        assert config.mode == RoutingMode.FIXED
        assert config.enabled is False
        assert config.threshold == 0.5
        assert config.strong_model is None
        assert config.weak_model is None

    def test_custom_values(self):
        config = RoutingConfig(
            step="summarization",
            mode=RoutingMode.DYNAMIC,
            enabled=True,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.7,
        )
        assert config.mode == RoutingMode.DYNAMIC
        assert config.enabled is True
        assert config.strong_model == "claude-sonnet-4-5"
        assert config.weak_model == "claude-haiku-4-5"
        assert config.threshold == 0.7


class TestModelConfigRouting:
    def test_loads_routing_from_yaml(self):
        """Verify routing configs are loaded from settings/models.yaml."""
        config = ModelConfig()
        rc = config.get_routing_config(ModelStep.SUMMARIZATION)
        assert rc.step == "summarization"
        assert rc.mode == RoutingMode.FIXED
        assert rc.enabled is False
        # These should be set from YAML
        assert rc.strong_model is not None
        assert rc.weak_model is not None

    def test_unconfigured_step_returns_default(self):
        """Steps not in routing: section get default RoutingConfig."""
        config = ModelConfig()
        # RERANKING is not in the routing section
        rc = config.get_routing_config(ModelStep.RERANKING)
        assert rc.step == "reranking"
        assert rc.mode == RoutingMode.FIXED
        assert rc.enabled is False

    def test_dynamic_routing_disabled_by_default(self):
        config = ModelConfig()
        assert config.is_dynamic_routing_enabled(ModelStep.SUMMARIZATION) is False

    def test_env_var_override_mode(self, monkeypatch):
        """ROUTING_SUMMARIZATION_MODE env var overrides YAML."""
        monkeypatch.setenv("ROUTING_SUMMARIZATION_MODE", "dynamic")
        config = ModelConfig()
        rc = config.get_routing_config(ModelStep.SUMMARIZATION)
        assert rc.mode == RoutingMode.DYNAMIC

    def test_env_var_invalid_mode_ignored(self, monkeypatch):
        """Invalid mode values in env vars are ignored."""
        monkeypatch.setenv("ROUTING_SUMMARIZATION_MODE", "invalid")
        config = ModelConfig()
        rc = config.get_routing_config(ModelStep.SUMMARIZATION)
        assert rc.mode == RoutingMode.FIXED

    def test_is_dynamic_requires_both_mode_and_enabled(self, monkeypatch):
        """Dynamic routing requires mode=dynamic AND enabled=True."""
        monkeypatch.setenv("ROUTING_SUMMARIZATION_MODE", "dynamic")
        config = ModelConfig()
        # Mode is dynamic but enabled is still False (from YAML)
        assert config.is_dynamic_routing_enabled(ModelStep.SUMMARIZATION) is False

    def test_get_routing_config_returns_routing_config(self):
        config = ModelConfig()
        rc = config.get_routing_config(ModelStep.DIGEST_CREATION)
        assert isinstance(rc, RoutingConfig)
        assert rc.step == "digest_creation"
