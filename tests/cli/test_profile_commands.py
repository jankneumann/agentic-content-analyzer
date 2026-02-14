"""Tests for profile CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestProfileList:
    @patch("src.cli.profile_commands.load_profile")
    @patch("src.cli.profile_commands.list_available_profiles")
    def test_list_profiles(self, mock_list, mock_load):
        mock_list.return_value = ["base", "local", "production"]

        mock_profile = MagicMock()
        mock_profile.extends = "base"
        mock_profile.description = "Test profile"
        mock_load.return_value = mock_profile

        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0
        assert "base" in result.output

    @patch("src.cli.profile_commands.list_available_profiles")
    def test_list_empty(self, mock_list):
        mock_list.return_value = []

        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0
        assert "No profiles found" in result.output


class TestProfileShow:
    @patch("src.cli.profile_commands.mask_secrets_in_dict")
    @patch("src.cli.profile_commands.load_secrets")
    @patch("src.cli.profile_commands.load_profile")
    def test_show_profile(self, mock_load, mock_secrets, mock_mask):
        mock_profile = MagicMock()
        mock_profile.name = "local"
        mock_profile.extends = "base"
        mock_profile.description = "Local development"
        mock_profile.providers.database = "local"
        mock_profile.providers.neo4j = "local"
        mock_profile.providers.storage = "local"
        mock_profile.providers.observability = "noop"
        mock_profile.settings.model_dump.return_value = {
            "database_url": "postgresql://localhost/test",
        }
        mock_load.return_value = mock_profile
        mock_secrets.return_value = {}
        mock_mask.return_value = {"database_url": "postgresql://localhost/test"}

        result = runner.invoke(app, ["profile", "show", "local"])
        assert result.exit_code == 0
        assert "local" in result.output

    @patch("src.cli.profile_commands.load_profile")
    def test_show_not_found(self, mock_load):
        from src.config.profiles import ProfileNotFoundError

        mock_load.side_effect = ProfileNotFoundError("nonexistent", available=["base", "local"])

        result = runner.invoke(app, ["profile", "show", "nonexistent"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestProfileValidate:
    @patch("src.cli.profile_commands.validate_profile")
    @patch("src.cli.profile_commands.load_profile")
    def test_validate_success(self, mock_load, mock_validate):
        mock_load.return_value = MagicMock()
        mock_validate.return_value = []

        result = runner.invoke(app, ["profile", "validate", "local"])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    @patch("src.cli.profile_commands.validate_profile")
    @patch("src.cli.profile_commands.load_profile")
    def test_validate_errors(self, mock_load, mock_validate):
        mock_load.return_value = MagicMock()
        mock_validate.return_value = ["Missing database_url", "Invalid provider"]

        result = runner.invoke(app, ["profile", "validate", "broken"])
        assert result.exit_code == 1
        assert "errors" in result.output.lower() or "Missing" in result.output


class TestProfileInspect:
    @patch("src.config.settings.Settings")
    @patch("src.config.settings.get_active_profile_name")
    def test_inspect_with_profile(self, mock_profile_name, mock_settings_cls):
        mock_profile_name.return_value = "local"

        mock_settings = MagicMock()
        mock_settings.environment = "development"
        mock_settings.database_provider = "local"
        mock_settings.neo4j_provider = "local"
        mock_settings.storage_provider = "local"
        mock_settings.observability_provider = "noop"
        mock_settings.get_effective_database_url.return_value = "postgresql://localhost/test"
        mock_settings._mask_url.return_value = "postgresql://localhost/test"
        mock_settings.get_effective_neo4j_uri.return_value = "bolt://localhost:7687"

        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings_cls.return_value = mock_settings

        result = runner.invoke(app, ["profile", "inspect"])
        assert result.exit_code == 0
        assert "local" in result.output

    @patch("src.config.settings.Settings")
    @patch("src.config.settings.get_active_profile_name")
    def test_inspect_no_profile(self, mock_profile_name, mock_settings_cls):
        mock_profile_name.return_value = None

        mock_settings = MagicMock()
        mock_settings.environment = "development"
        mock_settings.database_provider = "local"
        mock_settings.neo4j_provider = "local"
        mock_settings.observability_provider = "noop"
        mock_settings.get_effective_database_url.return_value = "postgresql://localhost/test"
        mock_settings._mask_url.return_value = "postgresql://localhost/test"
        mock_settings.get_effective_neo4j_uri.return_value = "bolt://localhost:7687"

        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings_cls.return_value = mock_settings

        result = runner.invoke(app, ["profile", "inspect"])
        assert result.exit_code == 0
        assert "none" in result.output.lower() or ".env" in result.output


class TestProfileMigrate:
    def test_migrate_file_not_found(self):
        result = runner.invoke(
            app,
            [
                "profile",
                "migrate",
                "--env-file",
                "/nonexistent/.env",
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_migrate_dry_run(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DATABASE_URL=postgresql://localhost/test\n"
            "ANTHROPIC_API_KEY=sk-ant-test123\n"
            "ENVIRONMENT=development\n"
        )

        result = runner.invoke(
            app,
            [
                "profile",
                "migrate",
                "--env-file",
                str(env_file),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "migrated" in result.output.lower() or "yaml" in result.output.lower()
