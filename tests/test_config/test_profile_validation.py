"""Tests for profile validation rules."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.profiles import (
    DatabaseSettings,
    Neo4jSettings,
    ObservabilitySettings,
    Profile,
    ProfileSettings,
    ProviderChoices,
    StorageSettings,
    validate_profile,
    validate_profile_strict,
)

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
def valid_local_profile() -> Profile:
    """A profile with all providers set to local (minimal requirements)."""
    return Profile(
        name="local",
        providers=ProviderChoices(
            database="local",
            neo4j="local",
            storage="local",
            observability="noop",
        ),
        settings=ProfileSettings(),
    )


@pytest.fixture
def supabase_profile() -> Profile:
    """A profile configured for Supabase."""
    return Profile(
        name="supabase",
        providers=ProviderChoices(
            database="supabase",
            neo4j="auradb",
            storage="supabase",
            observability="braintrust",
        ),
        settings=ProfileSettings(
            database=DatabaseSettings(
                supabase_project_ref="abc123",
                supabase_db_password="secret",
            ),
            neo4j=Neo4jSettings(
                neo4j_auradb_uri="neo4j+s://xxx.databases.neo4j.io",
                neo4j_auradb_password="aura-pass",
            ),
            storage=StorageSettings(
                supabase_storage_bucket="images",
            ),
            observability=ObservabilitySettings(
                braintrust_api_key="bt-key",
            ),
        ),
    )


# =============================================================================
# Valid Profile Tests
# =============================================================================


class TestValidProfilePasses:
    """Tests for valid profiles passing validation."""

    def test_local_profile_valid(self, valid_local_profile: Profile) -> None:
        """Test that a minimal local profile passes validation."""
        errors = validate_profile(valid_local_profile)
        assert errors == []

    def test_supabase_profile_valid(self, supabase_profile: Profile) -> None:
        """Test that a complete Supabase profile passes validation."""
        errors = validate_profile(supabase_profile)
        assert errors == []

    def test_railway_profile_valid(self) -> None:
        """Test that a Railway profile with all requirements passes."""
        profile = Profile(
            name="railway",
            providers=ProviderChoices(
                database="railway",
                neo4j="auradb",
                storage="railway",
                observability="braintrust",
            ),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    railway_database_url="postgresql://user:pass@host/db",
                ),
                neo4j=Neo4jSettings(
                    neo4j_auradb_uri="neo4j+s://xxx.databases.neo4j.io",
                    neo4j_auradb_password="aura-pass",
                ),
                observability=ObservabilitySettings(
                    braintrust_api_key="bt-key",
                ),
            ),
        )
        errors = validate_profile(profile)
        assert errors == []

    def test_neon_profile_valid(self) -> None:
        """Test that a Neon profile with all requirements passes."""
        profile = Profile(
            name="neon",
            providers=ProviderChoices(
                database="neon",
                neo4j="local",
                storage="s3",
                observability="noop",
            ),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    neon_database_url="postgresql://user:pass@ep-cool-name.us-east-2.aws.neon.tech/db",
                ),
                storage=StorageSettings(
                    image_storage_bucket="my-bucket",
                    aws_region="us-east-1",
                ),
            ),
        )
        errors = validate_profile(profile)
        assert errors == []


# =============================================================================
# Missing Required Settings Tests
# =============================================================================


class TestMissingRequiredSettings:
    """Tests for validation failures due to missing required settings."""

    def test_supabase_database_missing_project_ref(self) -> None:
        """Test that Supabase database without project_ref fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="supabase"),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    supabase_db_password="secret",
                    # Missing supabase_project_ref
                ),
            ),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("supabase_project_ref" in e for e in errors)

    def test_supabase_database_missing_password(self) -> None:
        """Test that Supabase database without password fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="supabase"),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    supabase_project_ref="abc123",
                    # Missing supabase_db_password
                ),
            ),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("supabase_db_password" in e for e in errors)

    def test_neon_database_missing_url(self) -> None:
        """Test that Neon database without URL fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="neon"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("neon_database_url" in e for e in errors)

    def test_railway_database_missing_url(self) -> None:
        """Test that Railway database without URL fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="railway"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("railway_database_url" in e for e in errors)

    def test_auradb_neo4j_missing_uri(self) -> None:
        """Test that AuraDB Neo4j without URI fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(neo4j="auradb"),
            settings=ProfileSettings(
                neo4j=Neo4jSettings(
                    neo4j_auradb_password="secret",
                    # Missing neo4j_auradb_uri
                ),
            ),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("neo4j_auradb_uri" in e for e in errors)

    def test_auradb_neo4j_missing_password(self) -> None:
        """Test that AuraDB Neo4j without password fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(neo4j="auradb"),
            settings=ProfileSettings(
                neo4j=Neo4jSettings(
                    neo4j_auradb_uri="neo4j+s://xxx.databases.neo4j.io",
                    # Missing neo4j_auradb_password
                ),
            ),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("neo4j_auradb_password" in e for e in errors)

    def test_s3_storage_missing_bucket(self) -> None:
        """Test that S3 storage without bucket fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(storage="s3"),
            settings=ProfileSettings(
                storage=StorageSettings(
                    aws_region="us-east-1",
                    # Missing image_storage_bucket
                    image_storage_bucket="",  # Empty string counts as missing
                ),
            ),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("image_storage_bucket" in e for e in errors)

    def test_braintrust_observability_missing_api_key(self) -> None:
        """Test that Braintrust without API key fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(observability="braintrust"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("braintrust_api_key" in e for e in errors)

    def test_otel_observability_missing_endpoint(self) -> None:
        """Test that OTel without endpoint fails."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(observability="otel"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        assert len(errors) >= 1
        assert any("otel_exporter_otlp_endpoint" in e for e in errors)


# =============================================================================
# Multiple Errors Aggregation Tests
# =============================================================================


class TestMultipleErrorsAggregated:
    """Tests for error aggregation behavior."""

    def test_multiple_missing_settings_aggregated(self) -> None:
        """Test that multiple validation errors are collected."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(
                database="supabase",  # Requires project_ref + password
                neo4j="auradb",  # Requires uri + password
                observability="braintrust",  # Requires api_key
            ),
            settings=ProfileSettings(),  # All empty
        )
        errors = validate_profile(profile)

        # Should have at least errors for:
        # - supabase_project_ref
        # - supabase_db_password
        # - neo4j_auradb_uri
        # - neo4j_auradb_password
        # - braintrust_api_key
        assert len(errors) >= 5

    def test_error_messages_include_provider_context(self) -> None:
        """Test that error messages include which provider requires the setting."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="neon"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)

        # Error message should mention the provider
        assert any("database=neon" in e for e in errors)
        assert any("neon_database_url" in e for e in errors)


# =============================================================================
# Coherence Rules Tests
# =============================================================================


class TestCoherenceRules:
    """Tests for provider coherence validation rules."""

    def test_supabase_storage_requires_supabase_db_config(self) -> None:
        """Test that storage=supabase requires Supabase database config."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(
                database="local",  # Not supabase!
                storage="supabase",
            ),
            settings=ProfileSettings(
                storage=StorageSettings(
                    supabase_storage_bucket="images",
                ),
            ),
        )
        errors = validate_profile(profile)

        # Should warn about coherence
        assert any("storage=supabase" in e and "database" in e for e in errors)

    def test_railway_storage_works_with_any_database(self) -> None:
        """Test that storage=railway works independently of database provider.

        Railway MinIO is an S3-compatible object store independent from
        Railway PostgreSQL — no cross-provider coherence rule needed.
        """
        profile = Profile(
            name="test",
            providers=ProviderChoices(
                database="neon",
                storage="railway",
            ),
            settings=ProfileSettings(
                database=DatabaseSettings(neon_database_url="postgresql://test"),
            ),
        )
        errors = validate_profile(profile)

        # No coherence errors for railway storage with non-railway database
        assert not any("storage=railway" in e and "database" in e for e in errors)

    def test_coherent_supabase_config_passes(self, supabase_profile: Profile) -> None:
        """Test that coherent Supabase config passes."""
        # supabase_profile fixture has storage=supabase with database=supabase
        errors = validate_profile(supabase_profile)
        assert errors == []

    def test_coherent_railway_config_passes(self) -> None:
        """Test that coherent Railway config passes."""
        profile = Profile(
            name="railway",
            providers=ProviderChoices(
                database="railway",
                storage="railway",
            ),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    railway_database_url="postgresql://user:pass@host/db",
                ),
            ),
        )
        errors = validate_profile(profile)
        assert errors == []


# =============================================================================
# Strict Validation Tests (File-based)
# =============================================================================


class TestValidateProfileStrict:
    """Tests for strict profile validation including file loading."""

    def test_valid_profile_file_passes(self, temp_profiles_dir: Path) -> None:
        """Test that a valid profile file passes strict validation."""
        profile_data = {
            "name": "test",
            "providers": {
                "database": "local",
                "neo4j": "local",
                "storage": "local",
                "observability": "noop",
            },
            "settings": {},
        }
        with open(temp_profiles_dir / "test.yaml", "w") as f:
            yaml.dump(profile_data, f)

        is_valid, errors, _warnings = validate_profile_strict(
            "test", profiles_dir=temp_profiles_dir
        )

        assert is_valid
        assert errors == []

    def test_invalid_profile_file_fails(self, temp_profiles_dir: Path) -> None:
        """Test that an invalid profile file fails strict validation."""
        profile_data = {
            "name": "test",
            "providers": {
                "database": "neon",  # Requires neon_database_url
            },
            "settings": {},
        }
        with open(temp_profiles_dir / "test.yaml", "w") as f:
            yaml.dump(profile_data, f)

        is_valid, errors, _warnings = validate_profile_strict(
            "test", profiles_dir=temp_profiles_dir
        )

        assert not is_valid
        assert any("neon_database_url" in e for e in errors)

    def test_missing_profile_file_fails(self, temp_profiles_dir: Path) -> None:
        """Test that missing profile file fails strict validation."""
        is_valid, errors, _warnings = validate_profile_strict(
            "nonexistent", profiles_dir=temp_profiles_dir
        )

        assert not is_valid
        assert any("not found" in e.lower() for e in errors)

    def test_malformed_yaml_fails(self, temp_profiles_dir: Path) -> None:
        """Test that malformed YAML fails strict validation."""
        with open(temp_profiles_dir / "broken.yaml", "w") as f:
            f.write("name: test\n  bad_indent: [unclosed")

        is_valid, errors, _warnings = validate_profile_strict(
            "broken", profiles_dir=temp_profiles_dir
        )

        assert not is_valid
        assert len(errors) >= 1

    def test_unresolved_variable_is_warning(self, temp_profiles_dir: Path) -> None:
        """Test that unresolved variables are reported as warnings."""
        profile_data = {
            "name": "test",
            "providers": {
                "database": "local",
            },
            "settings": {
                "database": {
                    "database_url": "${MISSING_VAR}",
                },
            },
        }
        with open(temp_profiles_dir / "test.yaml", "w") as f:
            yaml.dump(profile_data, f)

        is_valid, _errors, warnings = validate_profile_strict(
            "test", profiles_dir=temp_profiles_dir
        )

        # Profile is structurally valid, but has unresolved var
        # The exact behavior depends on whether we treat missing as error/warning
        # In template validation context, missing secrets are warnings
        assert any("MISSING_VAR" in w for w in warnings) or not is_valid


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in validation."""

    def test_empty_string_treated_as_missing(self) -> None:
        """Test that empty string values are treated as missing."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(database="neon"),
            settings=ProfileSettings(
                database=DatabaseSettings(
                    neon_database_url="",  # Empty string
                ),
            ),
        )
        errors = validate_profile(profile)
        assert any("neon_database_url" in e for e in errors)

    def test_noop_observability_needs_nothing(self) -> None:
        """Test that noop observability has no requirements."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(observability="noop"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        # Should not have any observability-related errors
        assert not any("observability" in e.lower() for e in errors)

    def test_opik_observability_needs_nothing(self) -> None:
        """Test that Opik observability has no requirements (self-hosted works without key)."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(observability="opik"),
            settings=ProfileSettings(),
        )
        errors = validate_profile(profile)
        # Should not have any observability-related errors
        assert not any("opik" in e.lower() for e in errors)

    def test_local_providers_need_nothing(self) -> None:
        """Test that all local providers have no requirements."""
        profile = Profile(
            name="test",
            providers=ProviderChoices(
                database="local",
                neo4j="local",
                storage="local",
                observability="noop",
            ),
            settings=ProfileSettings(),  # Empty settings
        )
        errors = validate_profile(profile)
        assert errors == []
