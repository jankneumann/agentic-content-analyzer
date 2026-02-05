"""Tests for profile CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from src.cli.profile_commands import app

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_profiles_dir(tmp_path: Path) -> Path:
    """Create a temporary profiles directory with test profiles."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    # Create a base profile
    base_profile = {
        "name": "base",
        "description": "Base test profile",
        "providers": {
            "database": "local",
            "neo4j": "local",
            "storage": "local",
            "observability": "noop",
        },
        "settings": {
            "environment": "development",
        },
    }
    with open(profiles_dir / "base.yaml", "w") as f:
        yaml.dump(base_profile, f)

    # Create a child profile
    child_profile = {
        "name": "child",
        "extends": "base",
        "description": "Child test profile",
        "settings": {
            "log_level": "DEBUG",
        },
    }
    with open(profiles_dir / "child.yaml", "w") as f:
        yaml.dump(child_profile, f)

    # Create an invalid profile (missing required settings for neon)
    invalid_profile = {
        "name": "invalid",
        "providers": {
            "database": "neon",
        },
        "settings": {},
    }
    with open(profiles_dir / "invalid.yaml", "w") as f:
        yaml.dump(invalid_profile, f)

    return profiles_dir


# =============================================================================
# List Command Tests
# =============================================================================


class TestListCommand:
    """Tests for profile list command."""

    def test_list_profiles(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test listing profiles."""
        result = runner.invoke(app, ["list", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 0
        assert "base" in result.output
        assert "child" in result.output
        assert "invalid" in result.output

    def test_list_shows_descriptions(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test that list shows profile descriptions."""
        result = runner.invoke(app, ["list", "--dir", str(temp_profiles_dir)])

        assert "Base test profile" in result.output

    def test_list_shows_extends(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test that list shows extends relationship."""
        result = runner.invoke(app, ["list", "--dir", str(temp_profiles_dir)])

        assert "extends: base" in result.output

    def test_list_empty_directory(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing an empty profiles directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["list", "--dir", str(empty_dir)])

        assert result.exit_code == 0
        assert "No profiles found" in result.output


# =============================================================================
# Show Command Tests
# =============================================================================


class TestShowCommand:
    """Tests for profile show command."""

    def test_show_profile(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test showing a profile."""
        result = runner.invoke(app, ["show", "base", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 0
        assert "Profile: base" in result.output
        assert "Providers:" in result.output
        assert "database: local" in result.output

    def test_show_profile_with_inheritance(
        self, runner: CliRunner, temp_profiles_dir: Path
    ) -> None:
        """Test showing a profile that extends another."""
        result = runner.invoke(app, ["show", "child", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 0
        assert "Profile: child" in result.output
        assert "Extends: base" in result.output

    def test_show_nonexistent_profile(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test showing a nonexistent profile."""
        result = runner.invoke(app, ["show", "nonexistent", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_raw_yaml(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test showing raw YAML without inheritance resolution."""
        result = runner.invoke(app, ["show", "child", "--raw", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 0
        # Raw output should show extends, not resolved inheritance
        assert "extends: base" in result.output


# =============================================================================
# Validate Command Tests
# =============================================================================


class TestValidateCommand:
    """Tests for profile validate command."""

    def test_validate_valid_profile(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test validating a valid profile."""
        result = runner.invoke(app, ["validate", "base", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_profile(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test validating an invalid profile."""
        result = runner.invoke(app, ["validate", "invalid", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 1
        assert "neon_database_url" in result.output

    def test_validate_nonexistent_profile(self, runner: CliRunner, temp_profiles_dir: Path) -> None:
        """Test validating a nonexistent profile."""
        result = runner.invoke(app, ["validate", "nonexistent", "--dir", str(temp_profiles_dir)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# =============================================================================
# Integration Tests with Real Profiles
# =============================================================================


class TestRealProfiles:
    """Tests using the actual project profiles."""

    def test_list_real_profiles(self, runner: CliRunner) -> None:
        """Test listing real project profiles."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Should have at least these profiles
        assert "base" in result.output
        assert "local" in result.output

    def test_validate_real_base_profile(self, runner: CliRunner) -> None:
        """Test validating the real base profile."""
        result = runner.invoke(app, ["validate", "base"])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_show_real_base_profile(self, runner: CliRunner) -> None:
        """Test showing the real base profile."""
        result = runner.invoke(app, ["show", "base"])

        assert result.exit_code == 0
        assert "Profile: base" in result.output
        assert "database: local" in result.output
