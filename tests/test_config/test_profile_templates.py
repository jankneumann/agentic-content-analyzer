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

    def test_railway_profile_variants_exist(self, profiles_dir: Path) -> None:
        """Railway has two explicit deployment variants — no implicit default."""
        for name in ("railway-falkordb.yaml", "railway-neo4j.yaml"):
            assert (profiles_dir / name).exists(), f"{name} profile not found"

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

    def test_railway_base_profile_loads(self, profiles_dir: Path) -> None:
        """`railway` is the shared base — supplies Railway compute/storage but no graphdb."""
        data = load_profile_raw("railway", profiles_dir)

        assert data["name"] == "railway"
        assert data.get("extends") == "base"

    def test_railway_neo4j_profile_loads(self, profiles_dir: Path) -> None:
        """railway-neo4j layers Neo4j AuraDB on top of the shared railway base."""
        data = load_profile_raw("railway-neo4j", profiles_dir)

        assert data["name"] == "railway-neo4j"
        assert data.get("extends") == "railway"

    def test_railway_falkordb_profile_loads(self, profiles_dir: Path) -> None:
        """railway-falkordb layers FalkorDB on top of the shared railway base."""
        data = load_profile_raw("railway-falkordb", profiles_dir)

        assert data["name"] == "railway-falkordb"
        assert data.get("extends") == "railway"

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
        assert profile.providers.observability == "langfuse"

    def test_local_profile_valid_structure(self, profiles_dir: Path) -> None:
        """Test that local profile has valid structure after inheritance."""
        profile = load_profile("local", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "local"
        # Should inherit providers from base
        assert profile.providers.database == "local"

    def test_railway_neo4j_profile_valid_structure(self, profiles_dir: Path) -> None:
        """railway-neo4j has valid structure with AuraDB graph backend."""
        profile = load_profile("railway-neo4j", profiles_dir=profiles_dir, skip_interpolation=True)

        assert isinstance(profile, Profile)
        assert profile.name == "railway-neo4j"
        assert profile.providers.database == "railway"
        assert profile.providers.graphdb == "neo4j"
        assert profile.providers.neo4j == "auradb"
        assert profile.providers.storage == "railway"
        assert profile.providers.observability == "langfuse"

    def test_railway_falkordb_profile_valid_structure(self, profiles_dir: Path) -> None:
        """railway-falkordb inherits Railway settings, overrides graphdb to FalkorDB."""
        profile = load_profile(
            "railway-falkordb", profiles_dir=profiles_dir, skip_interpolation=True
        )

        assert isinstance(profile, Profile)
        assert profile.name == "railway-falkordb"
        assert profile.providers.database == "railway"
        assert profile.providers.graphdb == "falkordb"
        assert profile.providers.storage == "railway"
        assert profile.providers.observability == "langfuse"

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
        assert profile.providers.observability == "langfuse"


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

    def test_railway_base_has_database_placeholders(self, profiles_dir: Path) -> None:
        """The shared `railway` base supplies the Railway PG database placeholders."""
        data = load_profile_raw("railway", profiles_dir)

        db_settings = data.get("settings", {}).get("database", {})
        assert "railway_database_url" in db_settings

    def test_railway_neo4j_has_auradb_placeholders(self, profiles_dir: Path) -> None:
        """railway-neo4j supplies the AuraDB credential placeholders."""
        data = load_profile_raw("railway-neo4j", profiles_dir)

        neo4j_settings = data.get("settings", {}).get("neo4j", {})
        assert "neo4j_auradb_uri" in neo4j_settings
        assert "neo4j_auradb_password" in neo4j_settings

    def test_railway_falkordb_has_falkordb_placeholders(self, profiles_dir: Path) -> None:
        """railway-falkordb supplies the FalkorDB connection placeholders."""
        data = load_profile_raw("railway-falkordb", profiles_dir)

        graphdb_settings = data.get("settings", {}).get("graphdb", {})
        assert "falkordb_cloud_host" in graphdb_settings
        assert "falkordb_cloud_port" in graphdb_settings

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
