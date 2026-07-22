"""Tests for Gemini batch-execution configuration loading.

Covers (spec scenarios: gemini-batch-execution "Opt-in per-step batch execution"):
- Default is OFF (sync) — zero behavior change unless explicitly opted in
- Requires BOTH the global switch AND per-step mode == 'batch'
- GEMINI_BATCH_ENABLED env var overrides the YAML global switch
- batch_config exposes flush/fallback thresholds
"""

import os

import pytest

from src.config.models import ModelConfig, ModelStep


@pytest.fixture(autouse=True)
def _clear_batch_env():
    """Isolate from any ambient GEMINI_BATCH_ENABLED."""
    saved = os.environ.pop("GEMINI_BATCH_ENABLED", None)
    yield
    if saved is not None:
        os.environ["GEMINI_BATCH_ENABLED"] = saved
    else:
        os.environ.pop("GEMINI_BATCH_ENABLED", None)


class TestIsBatchEnabled:
    def test_default_is_disabled(self):
        """Default YAML ships batch.enabled=false and all steps sync."""
        cfg = ModelConfig()
        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is False
        assert cfg.is_batch_enabled(ModelStep.YOUTUBE_PROCESSING) is False

    def test_requires_global_switch(self):
        """Per-step batch mode does nothing while the global switch is off."""
        cfg = ModelConfig()
        cfg._batch_config["enabled"] = False
        cfg._batch_config["execution"]["content_filtering"] = "batch"
        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is False

    def test_requires_step_mode_batch(self):
        """Global switch on but step still sync ⇒ disabled for that step."""
        cfg = ModelConfig()
        cfg._batch_config["enabled"] = True
        cfg._batch_config["execution"]["content_filtering"] = "sync"
        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is False

    def test_enabled_when_both_set(self):
        cfg = ModelConfig()
        cfg._batch_config["enabled"] = True
        cfg._batch_config["execution"]["content_filtering"] = "batch"
        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is True

    def test_env_var_enables_global_switch(self):
        os.environ["GEMINI_BATCH_ENABLED"] = "true"
        cfg = ModelConfig()
        assert cfg.batch_config["enabled"] is True

    def test_env_var_disables_global_switch(self):
        os.environ["GEMINI_BATCH_ENABLED"] = "false"
        cfg = ModelConfig()
        assert cfg.batch_config["enabled"] is False


class TestBatchConfigThresholds:
    def test_default_thresholds_present(self):
        cfg = ModelConfig()
        bc = cfg.batch_config
        assert bc["flush_max_requests"] == 50
        assert bc["flush_max_wait_minutes"] == 60
        assert bc["fallback_max_attempts"] == 1
        assert bc["inline_max_bytes"] == 18 * 1024 * 1024

    def test_batch_config_is_a_copy(self):
        """Mutating the returned dict must not corrupt internal state."""
        cfg = ModelConfig()
        cfg.batch_config["enabled"] = True
        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is False

    def test_batch_config_nested_execution_map_is_a_copy(self):
        cfg = ModelConfig()
        cfg._batch_config["enabled"] = True

        returned = cfg.batch_config
        returned["execution"]["content_filtering"] = "batch"

        assert cfg.is_batch_enabled(ModelStep.CONTENT_FILTERING) is False
