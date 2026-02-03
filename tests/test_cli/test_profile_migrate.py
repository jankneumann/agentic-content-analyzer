"""Tests for profile migrate command."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from src.cli.profile_commands import (
    _categorize_setting,
    _detect_providers,
    _is_secret_key,
    _parse_env_file,
    app,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_env_file(tmp_path: Path) -> Path:
    """Create a sample .env file for testing."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """# Database Configuration
DATABASE_PROVIDER=local
DATABASE_URL=postgresql://localhost/test

# Neo4j Configuration
NEO4J_PROVIDER=local
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=secret123

# API Keys
ANTHROPIC_API_KEY=sk-ant-test-key
OPENAI_API_KEY=sk-openai-test

# General Settings
ENVIRONMENT=development
LOG_LEVEL=DEBUG
"""
    )
    return env_file


@pytest.fixture
def profiles_output_dir(tmp_path: Path) -> Path:
    """Create a temporary profiles directory."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    return profiles_dir


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================


class TestSecretKeyDetection:
    """Tests for _is_secret_key helper."""

    def test_detects_api_key(self) -> None:
        """Test that API_KEY patterns are detected as secrets."""
        assert _is_secret_key("ANTHROPIC_API_KEY") is True
        assert _is_secret_key("openai_api_key") is True
        assert _is_secret_key("GOOGLE_KEY") is True

    def test_detects_password(self) -> None:
        """Test that PASSWORD patterns are detected as secrets."""
        assert _is_secret_key("DATABASE_PASSWORD") is True
        assert _is_secret_key("neo4j_password") is True

    def test_detects_secret(self) -> None:
        """Test that SECRET patterns are detected as secrets."""
        assert _is_secret_key("CLIENT_SECRET") is True
        assert _is_secret_key("aws_secret_access_key") is True

    def test_detects_token(self) -> None:
        """Test that TOKEN patterns are detected as secrets."""
        assert _is_secret_key("ACCESS_TOKEN") is True
        assert _is_secret_key("refresh_token") is True

    def test_detects_credential(self) -> None:
        """Test that CREDENTIAL patterns are detected as secrets."""
        assert _is_secret_key("GOOGLE_CREDENTIALS") is True

    def test_non_secrets_not_detected(self) -> None:
        """Test that regular settings are not detected as secrets."""
        assert _is_secret_key("DATABASE_URL") is False
        assert _is_secret_key("LOG_LEVEL") is False
        assert _is_secret_key("ENVIRONMENT") is False
        assert _is_secret_key("NEO4J_URI") is False

    def test_custom_patterns(self) -> None:
        """Test that custom patterns are respected."""
        assert _is_secret_key("MY_PRIVATE_VALUE") is False
        assert _is_secret_key("MY_PRIVATE_VALUE", extra_patterns=["PRIVATE"]) is True


class TestCategorizeSettings:
    """Tests for _categorize_setting helper."""

    def test_database_category(self) -> None:
        """Test database settings categorization."""
        assert _categorize_setting("DATABASE_URL") == "database"
        assert _categorize_setting("NEON_DATABASE_URL") == "database"
        assert _categorize_setting("REDIS_URL") == "database"
        assert _categorize_setting("SUPABASE_DB_URL") == "database"

    def test_neo4j_category(self) -> None:
        """Test Neo4j settings categorization."""
        assert _categorize_setting("NEO4J_URI") == "neo4j"
        assert _categorize_setting("NEO4J_USER") == "neo4j"
        assert _categorize_setting("GRAPHITI_ENABLED") == "neo4j"

    def test_storage_category(self) -> None:
        """Test storage settings categorization."""
        assert _categorize_setting("STORAGE_BUCKET") == "storage"
        assert _categorize_setting("IMAGE_STORAGE_PATH") == "storage"
        assert _categorize_setting("AWS_REGION") == "storage"
        assert _categorize_setting("S3_BUCKET") == "storage"

    def test_observability_category(self) -> None:
        """Test observability settings categorization.

        Note: Prefix matching happens before suffix matching, so BRAINTRUST_API_KEY
        is categorized as observability (not api_keys) because BRAINTRUST_ prefix
        is checked first.
        """
        assert _categorize_setting("OTEL_ENABLED") == "observability"
        assert _categorize_setting("BRAINTRUST_API_KEY") == "observability"  # Prefix wins
        assert _categorize_setting("OBSERVABILITY_LEVEL") == "observability"
        assert _categorize_setting("OPIK_ENABLED") == "observability"

    def test_api_keys_category(self) -> None:
        """Test API keys categorization."""
        assert _categorize_setting("ANTHROPIC_API_KEY") == "api_keys"
        assert _categorize_setting("OPENAI_KEY") == "api_keys"
        assert _categorize_setting("GOOGLE_SECRET") == "api_keys"

    def test_general_category(self) -> None:
        """Test general settings categorization."""
        assert _categorize_setting("ENVIRONMENT") == "general"
        assert _categorize_setting("LOG_LEVEL") == "general"
        assert _categorize_setting("DEBUG") == "general"


class TestProviderDetection:
    """Tests for _detect_providers helper."""

    def test_detects_all_providers(self) -> None:
        """Test that all provider types are detected."""
        variables = {
            "DATABASE_PROVIDER": "neon",
            "NEO4J_PROVIDER": "auradb",
            "STORAGE_PROVIDER": "s3",
            "OBSERVABILITY_PROVIDER": "braintrust",
        }
        providers = _detect_providers(variables)

        assert providers["database"] == "neon"
        assert providers["neo4j"] == "auradb"
        assert providers["storage"] == "s3"
        assert providers["observability"] == "braintrust"

    def test_detects_legacy_storage_provider(self) -> None:
        """Test that IMAGE_STORAGE_PROVIDER is detected as storage."""
        variables = {"IMAGE_STORAGE_PROVIDER": "local"}
        providers = _detect_providers(variables)

        assert providers["storage"] == "local"

    def test_storage_provider_takes_precedence(self) -> None:
        """Test that STORAGE_PROVIDER takes precedence over IMAGE_STORAGE_PROVIDER."""
        variables = {
            "STORAGE_PROVIDER": "s3",
            "IMAGE_STORAGE_PROVIDER": "local",
        }
        providers = _detect_providers(variables)

        assert providers["storage"] == "s3"

    def test_empty_providers_when_none_set(self) -> None:
        """Test that empty dict returned when no providers set."""
        variables = {"DATABASE_URL": "postgresql://localhost"}
        providers = _detect_providers(variables)

        assert providers == {}


class TestEnvFileParsing:
    """Tests for _parse_env_file helper."""

    def test_parses_key_value_pairs(self, tmp_path: Path) -> None:
        """Test basic key=value parsing."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")

        variables, _ = _parse_env_file(env_file)

        assert variables == {"FOO": "bar", "BAZ": "qux"}

    def test_handles_export_prefix(self, tmp_path: Path) -> None:
        """Test that 'export KEY=value' syntax is handled."""
        env_file = tmp_path / ".env"
        env_file.write_text("export FOO=bar\nexport BAZ=qux\nREGULAR=value\n")

        variables, _ = _parse_env_file(env_file)

        assert variables == {"FOO": "bar", "BAZ": "qux", "REGULAR": "value"}

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        """Test that quoted values are unquoted."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=\"bar baz\"\nBAZ='qux quux'\n")

        variables, _ = _parse_env_file(env_file)

        assert variables["FOO"] == "bar baz"
        assert variables["BAZ"] == "qux quux"

    def test_captures_comments(self, tmp_path: Path) -> None:
        """Test that comments are associated with variables."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nFOO=bar\n")

        variables, comments = _parse_env_file(env_file)

        assert "FOO" in comments
        assert comments["FOO"] == "This is a comment"

    def test_multiline_comments(self, tmp_path: Path) -> None:
        """Test that multi-line comments are joined."""
        env_file = tmp_path / ".env"
        env_file.write_text("# Line 1\n# Line 2\nFOO=bar\n")

        variables, comments = _parse_env_file(env_file)

        assert "Line 1" in comments["FOO"]
        assert "Line 2" in comments["FOO"]

    def test_empty_lines_reset_comments(self, tmp_path: Path) -> None:
        """Test that empty lines reset comment tracking."""
        env_file = tmp_path / ".env"
        env_file.write_text("# Comment 1\n\n# Comment 2\nFOO=bar\n")

        variables, comments = _parse_env_file(env_file)

        assert comments["FOO"] == "Comment 2"

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Test handling of empty file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        variables, comments = _parse_env_file(env_file)

        assert variables == {}
        assert comments == {}


# =============================================================================
# Integration Tests - Migrate Command
# =============================================================================


class TestMigrateCommand:
    """Tests for the migrate command."""

    def test_basic_migration_dry_run(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test basic migration with dry run."""
        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file), "--dry-run"],
        )

        assert result.exit_code == 0
        assert "profiles/migrated.yaml" in result.output
        assert "Dry run - no files created" in result.output

    def test_detects_providers_in_output(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test that providers are detected and included."""
        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file), "--dry-run"],
        )

        assert result.exit_code == 0
        assert "database: local" in result.output
        assert "neo4j: local" in result.output

    def test_separates_secrets(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test that secrets are separated from settings."""
        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file), "--dry-run"],
        )

        assert result.exit_code == 0
        # Secrets should be in .secrets.yaml section
        assert ".secrets.yaml" in result.output
        assert "ANTHROPIC_API_KEY" in result.output
        assert "NEO4J_PASSWORD" in result.output

    def test_custom_output_name(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test custom output profile name."""
        result = runner.invoke(
            app,
            [
                "migrate",
                "--env-file",
                str(sample_env_file),
                "--output",
                "custom-profile",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "profiles/custom-profile.yaml" in result.output
        assert "name: custom-profile" in result.output

    def test_preserves_comments_in_header(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test that comment preservation adds header."""
        result = runner.invoke(
            app,
            [
                "migrate",
                "--env-file",
                str(sample_env_file),
                "--preserve-comments",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert f"# Migrated from {sample_env_file}" in result.output

    def test_default_preserves_comments(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test that comments are preserved by default."""
        result = runner.invoke(
            app,
            [
                "migrate",
                "--env-file",
                str(sample_env_file),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        # By default, comments should be preserved (header should be present)
        assert "# Migrated from" in result.output

    def test_custom_secret_patterns(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test custom secret patterns."""
        env_file = tmp_path / ".env"
        env_file.write_text("MY_PRIVATE_VALUE=secret\nREGULAR_VALUE=public\n")

        result = runner.invoke(
            app,
            [
                "migrate",
                "--env-file",
                str(env_file),
                "--secret-patterns",
                "PRIVATE",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert ".secrets.yaml" in result.output
        assert "MY_PRIVATE_VALUE: secret" in result.output

    def test_creates_profile_file(
        self, runner: CliRunner, sample_env_file: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Test that profile file is created when not dry run."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Mock get_profiles_dir to use our temp directory
        monkeypatch.setattr(
            "src.cli.profile_commands.get_profiles_dir",
            lambda: profiles_dir,
        )

        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file)],
        )

        assert result.exit_code == 0
        assert "Created:" in result.output
        assert "Migration complete!" in result.output

        # Verify profile file was created
        profile_path = profiles_dir / "migrated.yaml"
        assert profile_path.exists()

        # Verify content
        with open(profile_path) as f:
            profile_data = yaml.safe_load(f)

        assert profile_data["name"] == "migrated"
        assert profile_data["extends"] == "base"

    def test_creates_secrets_file(
        self, runner: CliRunner, sample_env_file: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Test that secrets file is created when not dry run."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Change to temp dir so .secrets.yaml is created there
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "src.cli.profile_commands.get_profiles_dir",
            lambda: profiles_dir,
        )

        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file)],
        )

        assert result.exit_code == 0

        # Verify secrets file was created
        secrets_path = tmp_path / ".secrets.yaml"
        assert secrets_path.exists()

        # Verify content
        with open(secrets_path) as f:
            secrets_data = yaml.safe_load(f)

        assert "ANTHROPIC_API_KEY" in secrets_data
        assert "NEO4J_PASSWORD" in secrets_data

    def test_does_not_overwrite_existing_secrets(
        self, runner: CliRunner, sample_env_file: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Test that existing .secrets.yaml is not overwritten."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create existing secrets file
        existing_secrets = tmp_path / ".secrets.yaml"
        existing_secrets.write_text("EXISTING: value\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "src.cli.profile_commands.get_profiles_dir",
            lambda: profiles_dir,
        )

        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file)],
        )

        assert result.exit_code == 0
        assert "Warning:" in result.output
        assert "already exists" in result.output

        # Verify original content preserved
        with open(existing_secrets) as f:
            content = f.read()
        assert "EXISTING: value" in content

    def test_missing_env_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error handling for missing .env file."""
        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(tmp_path / "nonexistent.env")],
        )

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_empty_env_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of empty .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(env_file)],
        )

        assert result.exit_code == 0
        assert "No variables found" in result.output

    def test_env_file_with_only_comments(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of .env file with only comments."""
        env_file = tmp_path / ".env"
        env_file.write_text("# Just a comment\n# Another comment\n")

        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(env_file)],
        )

        assert result.exit_code == 0
        assert "No variables found" in result.output

    def test_generates_valid_yaml(self, runner: CliRunner, sample_env_file: Path) -> None:
        """Test that generated YAML is valid."""
        result = runner.invoke(
            app,
            ["migrate", "--env-file", str(sample_env_file), "--dry-run"],
        )

        assert result.exit_code == 0

        # Extract profile YAML section from output
        output = result.output
        profile_start = output.find("=== profiles/migrated.yaml ===")
        secrets_start = output.find("=== .secrets.yaml ===")

        if profile_start != -1 and secrets_start != -1:
            profile_yaml = output[profile_start:secrets_start]
            # Remove the header line
            profile_yaml = profile_yaml.split("\n", 1)[1]

            # Should be valid YAML
            profile_data = yaml.safe_load(profile_yaml)
            assert profile_data is not None
            assert "name" in profile_data
