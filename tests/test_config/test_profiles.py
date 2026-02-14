"""Tests for profile-based configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import yaml

from src.config.profiles import (
    Profile,
    ProfileInheritanceCycleError,
    ProfileNotFoundError,
    ProfileParseError,
    ProfileResolutionError,
    ProfileSettings,
    ProviderChoices,
    deep_merge,
    determine_active_profile,
    interpolate_dict,
    interpolate_value,
    list_available_profiles,
    load_profile,
    load_profile_raw,
    resolve_inheritance,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_profiles_dir(tmp_path: Path) -> Path:
    """Create a temporary profiles directory."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    return profiles_dir


@pytest.fixture
def base_profile_data() -> dict:
    """Base profile data for testing."""
    return {
        "name": "base",
        "description": "Base profile for testing",
        "providers": {
            "database": "local",
            "neo4j": "local",
            "storage": "local",
            "observability": "noop",
        },
        "settings": {
            "database": {
                "database_url": "postgresql://localhost/test",
            },
            "neo4j": {
                "neo4j_uri": "bolt://localhost:7687",
                "neo4j_password": "test_password",
            },
            "environment": "development",
            "log_level": "DEBUG",
        },
    }


@pytest.fixture
def child_profile_data() -> dict:
    """Child profile data that extends base."""
    return {
        "name": "child",
        "extends": "base",
        "description": "Child profile extending base",
        "providers": {
            "database": "railway",
        },
        "settings": {
            "database": {
                "railway_database_url": "${RAILWAY_DATABASE_URL}",
            },
            "log_level": "INFO",
        },
    }


# =============================================================================
# Model Tests
# =============================================================================


class TestProviderChoices:
    """Tests for ProviderChoices model."""

    def test_default_providers(self) -> None:
        """Test default provider values."""
        providers = ProviderChoices()
        assert providers.database == "local"
        assert providers.neo4j == "local"
        assert providers.storage == "local"
        assert providers.observability == "noop"

    def test_valid_database_providers(self) -> None:
        """Test all valid database provider values."""
        for provider in ["local", "supabase", "neon", "railway"]:
            providers = ProviderChoices(database=provider)
            assert providers.database == provider

    def test_valid_neo4j_providers(self) -> None:
        """Test all valid Neo4j provider values."""
        for provider in ["local", "auradb"]:
            providers = ProviderChoices(neo4j=provider)
            assert providers.neo4j == provider

    def test_valid_storage_providers(self) -> None:
        """Test all valid storage provider values."""
        for provider in ["local", "s3", "supabase", "railway"]:
            providers = ProviderChoices(storage=provider)
            assert providers.storage == provider

    def test_valid_observability_providers(self) -> None:
        """Test all valid observability provider values."""
        for provider in ["noop", "opik", "braintrust", "otel"]:
            providers = ProviderChoices(observability=provider)
            assert providers.observability == provider

    def test_invalid_provider_rejected(self) -> None:
        """Test that invalid provider values are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProviderChoices(database="invalid_provider")


class TestProfile:
    """Tests for Profile model."""

    def test_minimal_profile(self) -> None:
        """Test creating a profile with minimal required fields."""
        profile = Profile(name="test")
        assert profile.name == "test"
        assert profile.extends is None
        assert profile.description is None
        assert profile.providers.database == "local"

    def test_full_profile(self, base_profile_data: dict) -> None:
        """Test creating a profile with all fields."""
        profile = Profile.model_validate(base_profile_data)
        assert profile.name == "base"
        assert profile.description == "Base profile for testing"
        assert profile.providers.database == "local"
        assert profile.settings.database.database_url == "postgresql://localhost/test"

    def test_profile_with_extends(self, child_profile_data: dict) -> None:
        """Test creating a profile that extends another."""
        # Note: This doesn't resolve inheritance, just validates structure
        profile = Profile.model_validate(child_profile_data)
        assert profile.name == "child"
        assert profile.extends == "base"
        assert profile.providers.database == "railway"


class TestProfileSettings:
    """Tests for ProfileSettings model."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = ProfileSettings()
        assert settings.environment == "development"
        assert settings.log_level == "INFO"

    def test_nested_settings(self) -> None:
        """Test nested settings sections."""
        settings = ProfileSettings(
            database={"database_url": "postgresql://test"},
            neo4j={"neo4j_uri": "bolt://test"},
        )
        assert settings.database.database_url == "postgresql://test"
        assert settings.neo4j.neo4j_uri == "bolt://test"


# =============================================================================
# Interpolation Tests
# =============================================================================


class TestInterpolateValue:
    """Tests for environment variable interpolation."""

    def test_no_interpolation_needed(self) -> None:
        """Test value without variables passes through."""
        result = interpolate_value("plain text", {}, {}, "test")
        assert result == "plain text"

    def test_simple_variable(self) -> None:
        """Test simple ${VAR} interpolation."""
        result = interpolate_value(
            "url: ${DATABASE_URL}",
            {"DATABASE_URL": "postgres://localhost"},
            {},
            "test",
        )
        assert result == "url: postgres://localhost"

    def test_variable_from_secrets(self) -> None:
        """Test variable resolved from secrets dict."""
        result = interpolate_value(
            "${API_KEY}",
            {},
            {"API_KEY": "secret-key"},
            "test",
        )
        assert result == "secret-key"

    def test_env_var_takes_precedence(self) -> None:
        """Test environment variables take precedence over secrets."""
        result = interpolate_value(
            "${API_KEY}",
            {"API_KEY": "env-value"},
            {"API_KEY": "secret-value"},
            "test",
        )
        assert result == "env-value"

    def test_missing_required_variable(self) -> None:
        """Test missing required variable raises error."""
        with pytest.raises(ProfileResolutionError) as exc_info:
            interpolate_value("${MISSING_VAR}", {}, {}, "test", "settings.api_key")

        assert exc_info.value.variable == "MISSING_VAR"
        assert exc_info.value.profile_name == "test"
        assert "settings.api_key" in str(exc_info.value)

    def test_default_value(self) -> None:
        """Test ${VAR:-default} syntax."""
        result = interpolate_value(
            "${OPTIONAL_VAR:-default_value}",
            {},
            {},
            "test",
        )
        assert result == "default_value"

    def test_default_value_with_env_set(self) -> None:
        """Test default is not used when variable is set."""
        result = interpolate_value(
            "${OPTIONAL_VAR:-default_value}",
            {"OPTIONAL_VAR": "actual_value"},
            {},
            "test",
        )
        assert result == "actual_value"

    def test_escaped_variable(self) -> None:
        """Test $${VAR} escape produces literal ${VAR}."""
        result = interpolate_value(
            "$${NOT_INTERPOLATED}",
            {"NOT_INTERPOLATED": "should_not_appear"},
            {},
            "test",
        )
        assert result == "${NOT_INTERPOLATED}"

    def test_multiple_variables(self) -> None:
        """Test multiple variables in one string."""
        result = interpolate_value(
            "postgres://${USER}:${PASSWORD}@${HOST}/${DB}",
            {"USER": "admin", "PASSWORD": "secret", "HOST": "localhost", "DB": "mydb"},
            {},
            "test",
        )
        assert result == "postgres://admin:secret@localhost/mydb"

    def test_empty_default(self) -> None:
        """Test empty default value is allowed."""
        result = interpolate_value(
            "${OPTIONAL:-}",
            {},
            {},
            "test",
        )
        assert result == ""


class TestInterpolateDict:
    """Tests for recursive dictionary interpolation."""

    def test_nested_interpolation(self) -> None:
        """Test interpolation in nested dictionaries."""
        data = {
            "database": {
                "url": "${DATABASE_URL}",
                "pool_size": 5,
            },
            "name": "test",
        }
        result = interpolate_dict(
            data,
            {"DATABASE_URL": "postgres://test"},
            {},
            "test",
        )
        assert result["database"]["url"] == "postgres://test"
        assert result["database"]["pool_size"] == 5
        assert result["name"] == "test"

    def test_list_interpolation(self) -> None:
        """Test interpolation in lists."""
        data = {
            "urls": ["${URL1}", "${URL2}"],
        }
        result = interpolate_dict(
            data,
            {"URL1": "http://one", "URL2": "http://two"},
            {},
            "test",
        )
        assert result["urls"] == ["http://one", "http://two"]


# =============================================================================
# Profile Loading Tests
# =============================================================================


class TestLoadProfileRaw:
    """Tests for raw profile loading from YAML."""

    def test_load_valid_profile(self, temp_profiles_dir: Path, base_profile_data: dict) -> None:
        """Test loading a valid profile file."""
        profile_path = temp_profiles_dir / "base.yaml"
        with open(profile_path, "w") as f:
            yaml.dump(base_profile_data, f)

        data = load_profile_raw("base", temp_profiles_dir)
        assert data["name"] == "base"
        assert data["providers"]["database"] == "local"

    def test_profile_not_found(self, temp_profiles_dir: Path) -> None:
        """Test loading a non-existent profile."""
        with pytest.raises(ProfileNotFoundError) as exc_info:
            load_profile_raw("nonexistent", temp_profiles_dir)

        assert exc_info.value.profile_name == "nonexistent"

    def test_available_profiles_in_error(
        self, temp_profiles_dir: Path, base_profile_data: dict
    ) -> None:
        """Test that error message lists available profiles."""
        # Create a profile
        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)

        with pytest.raises(ProfileNotFoundError) as exc_info:
            load_profile_raw("nonexistent", temp_profiles_dir)

        assert "base" in exc_info.value.available

    def test_invalid_yaml(self, temp_profiles_dir: Path) -> None:
        """Test loading profile with invalid YAML syntax."""
        profile_path = temp_profiles_dir / "invalid.yaml"
        with open(profile_path, "w") as f:
            f.write("name: test\n  invalid: [unclosed")

        with pytest.raises(ProfileParseError) as exc_info:
            load_profile_raw("invalid", temp_profiles_dir)

        assert exc_info.value.profile_name == "invalid"
        assert exc_info.value.line is not None

    def test_profiles_dir_not_found(self, tmp_path: Path) -> None:
        """Test error when profiles directory doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent"

        with pytest.raises(ProfileNotFoundError):
            load_profile_raw("any", nonexistent_dir)


class TestListAvailableProfiles:
    """Tests for listing available profiles."""

    def test_list_profiles(self, temp_profiles_dir: Path, base_profile_data: dict) -> None:
        """Test listing available profiles."""
        # Create some profiles
        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)
        with open(temp_profiles_dir / "production.yaml", "w") as f:
            yaml.dump({"name": "production"}, f)

        with patch.dict(os.environ, {"PROFILES_DIR": str(temp_profiles_dir)}):
            profiles = list_available_profiles()

        assert "base" in profiles
        assert "production" in profiles

    def test_ignores_underscore_prefixed(self, temp_profiles_dir: Path) -> None:
        """Test that _prefixed files are ignored."""
        with open(temp_profiles_dir / "_defaults.yaml", "w") as f:
            yaml.dump({"key": "value"}, f)
        with open(temp_profiles_dir / "valid.yaml", "w") as f:
            yaml.dump({"name": "valid"}, f)

        with patch.dict(os.environ, {"PROFILES_DIR": str(temp_profiles_dir)}):
            profiles = list_available_profiles()

        assert "valid" in profiles
        assert "_defaults" not in profiles


# =============================================================================
# Inheritance Tests
# =============================================================================


class TestDeepMerge:
    """Tests for deep merge functionality."""

    def test_simple_merge(self) -> None:
        """Test merging flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test merging nested dictionaries."""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}
        result = deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_list_replacement(self) -> None:
        """Test that lists are replaced, not merged."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"items": [4, 5]}


class TestResolveInheritance:
    """Tests for profile inheritance resolution."""

    def test_no_inheritance(self, temp_profiles_dir: Path, base_profile_data: dict) -> None:
        """Test loading profile without inheritance."""
        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)

        data = resolve_inheritance("base", temp_profiles_dir)
        assert data["name"] == "base"

    def test_single_level_inheritance(
        self,
        temp_profiles_dir: Path,
        base_profile_data: dict,
        child_profile_data: dict,
    ) -> None:
        """Test single-level inheritance."""
        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)
        with open(temp_profiles_dir / "child.yaml", "w") as f:
            yaml.dump(child_profile_data, f)

        data = resolve_inheritance("child", temp_profiles_dir)

        # Child overrides
        assert data["name"] == "child"
        assert data["providers"]["database"] == "railway"
        assert data["settings"]["log_level"] == "INFO"

        # Inherited from base
        assert data["providers"]["neo4j"] == "local"

    def test_multi_level_inheritance(self, temp_profiles_dir: Path) -> None:
        """Test grandparent -> parent -> child inheritance."""
        grandparent = {
            "name": "grandparent",
            "providers": {"database": "local"},
            "settings": {"a": 1, "b": 2, "c": 3},
        }
        parent = {
            "name": "parent",
            "extends": "grandparent",
            "settings": {"b": 20},
        }
        child = {
            "name": "child",
            "extends": "parent",
            "settings": {"c": 300},
        }

        with open(temp_profiles_dir / "grandparent.yaml", "w") as f:
            yaml.dump(grandparent, f)
        with open(temp_profiles_dir / "parent.yaml", "w") as f:
            yaml.dump(parent, f)
        with open(temp_profiles_dir / "child.yaml", "w") as f:
            yaml.dump(child, f)

        data = resolve_inheritance("child", temp_profiles_dir)

        assert data["name"] == "child"
        assert data["settings"]["a"] == 1  # From grandparent
        assert data["settings"]["b"] == 20  # From parent
        assert data["settings"]["c"] == 300  # From child

    def test_circular_inheritance_detected(self, temp_profiles_dir: Path) -> None:
        """Test that circular inheritance is detected."""
        profile_a = {"name": "a", "extends": "b"}
        profile_b = {"name": "b", "extends": "a"}

        with open(temp_profiles_dir / "a.yaml", "w") as f:
            yaml.dump(profile_a, f)
        with open(temp_profiles_dir / "b.yaml", "w") as f:
            yaml.dump(profile_b, f)

        with pytest.raises(ProfileInheritanceCycleError) as exc_info:
            resolve_inheritance("a", temp_profiles_dir)

        assert "a" in exc_info.value.cycle_path
        assert "b" in exc_info.value.cycle_path

    def test_missing_parent(self, temp_profiles_dir: Path, child_profile_data: dict) -> None:
        """Test error when parent profile doesn't exist."""
        with open(temp_profiles_dir / "child.yaml", "w") as f:
            yaml.dump(child_profile_data, f)

        with pytest.raises(ProfileNotFoundError) as exc_info:
            resolve_inheritance("child", temp_profiles_dir)

        assert exc_info.value.profile_name == "base"


class TestLoadProfile:
    """Tests for full profile loading with interpolation."""

    def test_load_with_interpolation(
        self, temp_profiles_dir: Path, base_profile_data: dict
    ) -> None:
        """Test loading profile with variable interpolation."""
        base_profile_data["settings"]["database"]["url"] = "${DATABASE_URL}"

        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)

        profile = load_profile(
            "base",
            secrets={},
            env_vars={"DATABASE_URL": "postgres://resolved"},
            profiles_dir=temp_profiles_dir,
        )

        assert profile.settings.database.model_extra.get("url") == "postgres://resolved"

    def test_load_skip_interpolation(
        self, temp_profiles_dir: Path, base_profile_data: dict
    ) -> None:
        """Test loading profile without interpolation for validation."""
        base_profile_data["settings"]["database"]["url"] = "${MISSING_VAR}"

        with open(temp_profiles_dir / "base.yaml", "w") as f:
            yaml.dump(base_profile_data, f)

        # Should not raise even though variable is missing
        profile = load_profile(
            "base",
            profiles_dir=temp_profiles_dir,
            skip_interpolation=True,
        )

        assert "${MISSING_VAR}" in str(profile.settings.database.model_extra.get("url"))


# =============================================================================
# Profile Resolution Order Tests
# =============================================================================


class TestDetermineActiveProfile:
    """Tests for determining active profile."""

    def test_profile_from_env_var(self, temp_profiles_dir: Path) -> None:
        """Test PROFILE env var takes precedence."""
        with patch.dict(
            os.environ,
            {"PROFILE": "custom", "PROFILES_DIR": str(temp_profiles_dir)},
        ):
            name = determine_active_profile()

        assert name == "custom"

    def test_default_profile_fallback(self, temp_profiles_dir: Path) -> None:
        """Test fallback to default.yaml."""
        with open(temp_profiles_dir / "default.yaml", "w") as f:
            yaml.dump({"name": "default"}, f)

        with patch.dict(
            os.environ,
            {"PROFILES_DIR": str(temp_profiles_dir)},
            clear=False,
        ):
            # Remove PROFILE if set
            os.environ.pop("PROFILE", None)
            name = determine_active_profile()

        assert name == "default"

    def test_no_profile_returns_none(self, temp_profiles_dir: Path) -> None:
        """Test None returned when no profile configured."""
        with patch.dict(
            os.environ,
            {"PROFILES_DIR": str(temp_profiles_dir)},
            clear=False,
        ):
            os.environ.pop("PROFILE", None)
            name = determine_active_profile()

        assert name is None
