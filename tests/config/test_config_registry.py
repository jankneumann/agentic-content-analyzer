"""Tests for ConfigRegistry — settings-mgmt scenarios 1-6b."""

from pathlib import Path

import pytest
import yaml

from src.config.config_registry import ConfigDomain, ConfigRegistry


@pytest.fixture
def settings_dir(tmp_path: Path) -> Path:
    """Create a temporary settings directory with test YAML files."""
    d = tmp_path / "settings"
    d.mkdir()

    # prompts.yaml — nested structure
    (d / "prompts.yaml").write_text(
        yaml.dump(
            {
                "chat": {
                    "summary": {"system": "You are a helpful assistant."},
                    "digest": {"system": "You are a digest reviewer."},
                },
                "pipeline": {"summarization": {"system": "Summarize this."}},
            }
        )
    )

    # models.yaml — flat + nested
    (d / "models.yaml").write_text(
        yaml.dump(
            {
                "models": {"claude-haiku": {"family": "claude", "name": "Haiku"}},
                "default_models": {"summarization": "claude-haiku"},
            }
        )
    )

    # voice.yaml
    (d / "voice.yaml").write_text(
        yaml.dump(
            {
                "provider": "openai",
                "default_voice": "nova",
                "speed": 1.0,
                "presets": {
                    "professional": {"openai": "onyx"},
                    "warm": {"openai": "nova"},
                },
            }
        )
    )

    # notifications.yaml
    (d / "notifications.yaml").write_text(
        yaml.dump({"defaults": {"batch_summary": True, "job_failure": True}})
    )

    return d


@pytest.fixture
def registry(settings_dir: Path) -> ConfigRegistry:
    """Create a ConfigRegistry with standard test domains registered."""
    reg = ConfigRegistry(settings_dir=settings_dir)
    reg.register(ConfigDomain(name="prompts", yaml_file="prompts.yaml"))
    reg.register(ConfigDomain(name="models", yaml_file="models.yaml"))
    reg.register(ConfigDomain(name="voice", yaml_file="voice.yaml"))
    reg.register(ConfigDomain(name="notifications", yaml_file="notifications.yaml"))
    return reg


class TestDomainRegistration:
    """settings-mgmt.1 — Domain registration (lazy loading)."""

    def test_register_domain_lazy_no_file_read(self, settings_dir: Path) -> None:
        """YAML file SHALL NOT be opened until first get() call."""
        reg = ConfigRegistry(settings_dir=settings_dir)
        reg.register(ConfigDomain(name="prompts", yaml_file="prompts.yaml"))
        # Cache should be empty — no file read yet
        assert "prompts" not in reg._cache
        assert "prompts" in reg.registered_domains

    def test_register_duplicate_domain_raises_valueerror(self, registry: ConfigRegistry) -> None:
        """settings-mgmt.1a — Duplicate registration SHALL raise ValueError."""
        with pytest.raises(ValueError, match="already registered"):
            registry.register(ConfigDomain(name="prompts", yaml_file="prompts.yaml"))


class TestDefaultValueResolution:
    """settings-mgmt.2 — Default value resolution."""

    def test_get_nested_key_returns_leaf_value(self, registry: ConfigRegistry) -> None:
        """Dot-separated key path SHALL resolve to leaf value."""
        result = registry.get("prompts", "chat.summary.system")
        assert result == "You are a helpful assistant."

    def test_get_caches_after_first_load(self, registry: ConfigRegistry) -> None:
        """YAML file SHALL be cached after first load."""
        registry.get("prompts", "chat.summary.system")
        assert "prompts" in registry._cache

    def test_get_top_level_key(self, registry: ConfigRegistry) -> None:
        """Top-level keys work without dots."""
        assert registry.get("voice", "provider") == "openai"
        assert registry.get("voice", "speed") == 1.0

    def test_get_nested_dict_returns_dict(self, registry: ConfigRegistry) -> None:
        """Non-leaf keys return the dict subtree."""
        result = registry.get("prompts", "chat.summary")
        assert isinstance(result, dict)
        assert result["system"] == "You are a helpful assistant."


class TestCacheInvalidation:
    """settings-mgmt.3 — Cache invalidation via reload."""

    def test_reload_invalidates_cache_reads_fresh(
        self, registry: ConfigRegistry, settings_dir: Path
    ) -> None:
        """After reload(), get() SHALL return values from the reloaded file."""
        # Load initial value
        assert registry.get("voice", "provider") == "openai"

        # Modify YAML on disk
        voice_path = settings_dir / "voice.yaml"
        data = yaml.safe_load(voice_path.read_text())
        data["provider"] = "elevenlabs"
        voice_path.write_text(yaml.dump(data))

        # Before reload — cached value
        assert registry.get("voice", "provider") == "openai"

        # After reload — fresh value
        registry.reload("voice")
        assert registry.get("voice", "provider") == "elevenlabs"

    def test_reload_all(self, registry: ConfigRegistry) -> None:
        """reload_all() SHALL reload every domain."""
        # Trigger initial load
        registry.get("prompts", "chat.summary.system")
        registry.get("voice", "provider")
        assert len(registry._cache) >= 2

        registry.reload_all()
        # Cache repopulated
        assert len(registry._cache) == 4


class TestMissingKeys:
    """settings-mgmt.4, 4a — Missing and null keys."""

    def test_get_missing_key_returns_none(self, registry: ConfigRegistry) -> None:
        """Missing key SHALL return None without raising."""
        assert registry.get("voice", "nonexistent.key") is None

    def test_get_missing_intermediate_key_returns_none(self, registry: ConfigRegistry) -> None:
        """Missing intermediate path element SHALL return None."""
        assert registry.get("prompts", "chat.nonexistent.system") is None

    def test_get_null_yaml_value_returns_none(self, settings_dir: Path) -> None:
        """settings-mgmt.4a — Null YAML value SHALL return None."""
        (settings_dir / "nulltest.yaml").write_text(yaml.dump({"chat": {"summary": None}}))
        reg = ConfigRegistry(settings_dir=settings_dir)
        reg.register(ConfigDomain(name="nulltest", yaml_file="nulltest.yaml"))
        assert reg.get("nulltest", "chat.summary") is None


class TestListKeys:
    """settings-mgmt.5 — List all keys in domain."""

    def test_list_keys_returns_only_leaf_paths(self, registry: ConfigRegistry) -> None:
        """Only leaf-node (non-dict) keys SHALL appear."""
        keys = registry.list_keys("notifications")
        assert "defaults.batch_summary" in keys
        assert "defaults.job_failure" in keys
        # Intermediate node should NOT appear
        assert "defaults" not in keys

    def test_list_keys_nested_structure(self, registry: ConfigRegistry) -> None:
        """Deeply nested YAML produces correct leaf paths."""
        keys = registry.list_keys("prompts")
        assert "chat.summary.system" in keys
        assert "chat.digest.system" in keys
        assert "pipeline.summarization.system" in keys
        # Intermediate nodes absent
        assert "chat" not in keys
        assert "chat.summary" not in keys


class TestErrorHandling:
    """settings-mgmt.6, 6a, 6b — Error scenarios."""

    def test_get_unregistered_domain_raises_valueerror(self, registry: ConfigRegistry) -> None:
        """settings-mgmt.6 — Unregistered domain SHALL raise ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            registry.get("unknown_domain", "key")

    def test_get_malformed_yaml_raises_yamlerror(self, settings_dir: Path) -> None:
        """settings-mgmt.6a — Invalid YAML syntax SHALL raise YAMLError."""
        (settings_dir / "broken.yaml").write_text("{ invalid: yaml: [")
        reg = ConfigRegistry(settings_dir=settings_dir)
        reg.register(ConfigDomain(name="broken", yaml_file="broken.yaml"))
        with pytest.raises(yaml.YAMLError):
            reg.get("broken", "any.key")

    def test_get_missing_file_raises_filenotfounderror(self, settings_dir: Path) -> None:
        """settings-mgmt.6b — Missing file SHALL raise FileNotFoundError."""
        reg = ConfigRegistry(settings_dir=settings_dir)
        reg.register(ConfigDomain(name="missing", yaml_file="does_not_exist.yaml"))
        with pytest.raises(FileNotFoundError, match="does_not_exist.yaml"):
            reg.get("missing", "any.key")


class TestGetRaw:
    """Test get_raw() for full tree access."""

    def test_get_raw_returns_full_dict(self, registry: ConfigRegistry) -> None:
        """get_raw() SHALL return the entire parsed YAML dict."""
        raw = registry.get_raw("notifications")
        assert isinstance(raw, dict)
        assert "defaults" in raw
        assert raw["defaults"]["batch_summary"] is True
