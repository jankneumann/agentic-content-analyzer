"""Tests for default profile templates structural correctness."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.profiles import (
    Profile,
    load_profile,
    load_profile_raw,
    validate_profile,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def profiles_dir() -> Path:
    """Get the actual profiles directory."""
    return Path(__file__).parent.parent.parent / "profiles"


# =============================================================================
# Template Existence Tests
# =============================================================================


class TestProfileTemplatesExist:
    """Tests for profile template files existing."""

    def test_profiles_directory_exists(self, profiles_dir: Path) -> None:
        """Test that profiles directory exists."""
        assert profiles_dir.exists(), f"Profiles directory not found: {profiles_dir}"
        assert profiles_dir.is_dir()

    def test_base_profile_exists(self, profiles_dir: Path) -> None:
        """Test that base.yaml exists."""
        base_path = profiles_dir / "base.yaml"
        assert base_path.exists(), "base.yaml profile not found"

    def test_local_profile_exists(self, profiles_dir: Path) -> None:
        """Test that local.yaml exists."""
        local_path = profiles_dir / "local.yaml"
        assert local_path.exists(), "local.yaml profile not found"

    def test_railway_profile_exists(self, profiles_dir: Path) -> None:
        """Test that railway.yaml exists."""
        railway_path = profiles_dir / "railway.yaml"
        assert railway_path.exists(), "railway.yaml profile not found"

    def test_supabase_cloud_profile_exists(self, profiles_dir: Path) -> None:
        """Test that supabase-cloud.yaml exists."""
        supabase_path = profiles_dir / "supabase-cloud.yaml"
        assert supabase_path.exists(), "supabase-cloud.yaml profile not found"

    def test_local_supabase_profile_exists(self, profiles_dir: Path) -> None:
        """Test that local-supabase.yaml exists."""
        path = profiles_dir / "local-supabase.yaml"
        assert path.exists(), "local-supabase.yaml profile not found"


# =============================================================================
# Structural Validity Tests
# =============================================================================


class TestProfileTemplatesStructure:
    """Tests for profile template structural validity."""

    def test_base_profile_loads(self, profiles_dir: Path) -> None:
        """Test that base profile loads without structural errors."""
        data = load_profile_raw("base", profiles_dir)

        assert "name" in data
        assert data["name"] == "base"
        assert "providers" in data
        assert "settings" in data

    def test_local_profile_loads(self, profiles_dir: Path) -> None:
        """Test that local profile loads and extends base."""
        data = load_profile_raw("local", profiles_dir)

        assert data["name"] == "local"
        assert data.get("extends") == "base"

    def test_railway_profile_loads(self, profiles_dir: Path) -> None:
        """Test that railway profile loads and extends base."""
        data = load_profile_raw("railway", profiles_dir)

        assert data["name"] == "railway"
        assert data.get("extends") == "base"

    def test_supabase_cloud_profile_loads(self, profiles_dir: Path) -> None:
        """Test that supabase-cloud profile loads and extends base."""
        data = load_profile_raw("supabase-cloud", profiles_dir)

        assert data["name"] == "supabase-cloud"
        assert data.get("extends") == "base"

    def test_local_supabase_profile_loads(self, profiles_dir: Path) -> None:
        """Test that local-supabase profile loads and extends local."""
        data = load_profile_raw("local-supabase", profiles_dir)

        assert data["name"] == "local-supabase"
        assert data.get("extends") == "local"


class TestProfileTemplatesValidation:
    """Tests for profile template validation (skip interpolation)."""

    def test_base_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that base profile has valid structure."""
        profile = load_profile("base", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "base"
        assert profile.providers.database == "local"
        assert profile.providers.neo4j == "local"
        assert profile.providers.storage == "local"
        assert profile.providers.observability == "noop"

    def test_local_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that local profile has valid structure after inheritance."""
        profile = load_profile("local", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "local"
        # Should inherit providers from base
        assert profile.providers.database == "local"

    def test_railway_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that railway profile has valid structure."""
        profile = load_profile("railway", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "railway"
        assert profile.providers.database == "railway"
        assert profile.providers.neo4j == "auradb"
        assert profile.providers.storage == "railway"
        assert profile.providers.observability == "braintrust"

    def test_supabase_cloud_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that supabase-cloud profile has valid structure."""
        profile = load_profile("supabase-cloud", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "supabase-cloud"
        assert profile.providers.database == "supabase"
        assert profile.providers.neo4j == "auradb"
        assert profile.providers.storage == "supabase"

    def test_local_supabase_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that local-supabase profile has valid structure after inheritance."""
        profile = load_profile("local-supabase", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "local-supabase"
        # Should override providers to supabase
        assert profile.providers.database == "supabase"
        assert profile.providers.storage == "supabase"
        # Should inherit neo4j and observability from local/base
        assert profile.providers.neo4j == "local"
        assert profile.providers.observability == "noop"


class TestProfileTemplatesHaveRequiredFields:
    """Tests that profiles have required fields for their providers."""

    def test_base_profile_has_local_defaults(self, profiles_dir: Path) -> None:
        """Test that base profile has local provider defaults."""
        profile = load_profile("base", profiles_dir=profiles_dir, skip_interpolation=True)

        # Local providers don't require additional settings
        errors = validate_profile(profile, check_secrets=False)
        assert errors == [], f"Base profile validation errors: {errors}"

    def test_local_profile_validates(self, profiles_dir: Path) -> None:
        """Test that local profile validates."""
        profile = load_profile("local", profiles_dir=profiles_dir, skip_interpolation=True)

        errors = validate_profile(profile, check_secrets=False)
        assert errors == [], f"Local profile validation errors: {errors}"

    def test_railway_profile_has_required_placeholders(self, profiles_dir: Path) -> None:
        """Test that railway profile has placeholders for required settings."""
        data = load_profile_raw("railway", profiles_dir)

        settings = data.get("settings", {})
        db_settings = settings.get("database", {})
        neo4j_settings = settings.get("neo4j", {})

        # Should have placeholders for Railway and AuraDB settings
        assert "railway_database_url" in db_settings
        assert "neo4j_auradb_uri" in neo4j_settings
        assert "neo4j_auradb_password" in neo4j_settings

    def test_local_supabase_profile_has_supabase_local(self, profiles_dir: Path) -> None:
        """Test that local-supabase profile sets supabase_local: true."""
        data = load_profile_raw("local-supabase", profiles_dir)

        settings = data.get("settings", {})
        db_settings = settings.get("database", {})

        assert db_settings.get("supabase_local") is True

    def test_supabase_cloud_profile_has_required_placeholders(self, profiles_dir: Path) -> None:
        """Test that supabase-cloud profile has placeholders for required settings."""
        data = load_profile_raw("supabase-cloud", profiles_dir)

        settings = data.get("settings", {})
        db_settings = settings.get("database", {})
        storage_settings = settings.get("storage", {})

        # Should have placeholders for Supabase settings
        assert "supabase_project_ref" in db_settings
        assert "supabase_db_password" in db_settings
        assert "supabase_access_key_id" in storage_settings
