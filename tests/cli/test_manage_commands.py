"""Tests for manage CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestSetupGmail:
    @patch("src.ingestion.gmail.GmailClient")
    def test_setup_gmail_success(self, mock_cls):
        mock_cls.return_value = MagicMock()

        result = runner.invoke(app, ["manage", "setup-gmail"])
        assert result.exit_code == 0
        assert "Gmail OAuth setup initiated" in result.output

    @patch("src.ingestion.gmail.GmailClient")
    def test_setup_gmail_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("No credentials")

        result = runner.invoke(app, ["manage", "setup-gmail"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestVerifySetup:
    @patch("src.storage.graphiti_client.GraphitiClient")
    @patch("src.config.settings")
    @patch("src.storage.database.get_db")
    def test_verify_all_pass(self, mock_get_db, mock_settings, mock_graphiti):
        # Mock settings as a module with attributes
        mock_settings.anthropic_api_key = "sk-ant-real-key"

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["manage", "verify-setup"])
        assert result.exit_code == 0
        assert "Pass" in result.output or "pass" in result.output

    @patch("src.storage.database.get_db")
    def test_verify_db_fail(self, mock_get_db):
        mock_get_db.side_effect = RuntimeError("Connection refused")

        result = runner.invoke(app, ["manage", "verify-setup"])
        assert result.exit_code == 0  # verify-setup always completes, just reports fails
        assert "Fail" in result.output or "fail" in result.output


class TestRailwaySync:
    def test_railway_sync(self):
        result = runner.invoke(app, ["manage", "railway-sync"])
        assert result.exit_code == 0
        assert "railway up" in result.output.lower() or "Railway" in result.output


class TestCheckProfileSecrets:
    @patch("src.config.settings.get_active_profile_name")
    def test_no_profile_active(self, mock_profile_name):
        mock_profile_name.return_value = None

        result = runner.invoke(app, ["manage", "check-profile-secrets"])
        assert result.exit_code == 0
        assert "No profile active" in result.output

    @patch("src.config.profiles.load_profile")
    @patch("src.config.settings.get_active_profile_name")
    def test_all_secrets_resolved(self, mock_profile_name, mock_load):
        mock_profile_name.return_value = "local"
        mock_profile = MagicMock()
        mock_profile.settings.model_dump.return_value = {
            "database_url": "postgresql://localhost/test",
            "api_key": "resolved-value",
        }
        mock_load.return_value = mock_profile

        result = runner.invoke(app, ["manage", "check-profile-secrets"])
        assert result.exit_code == 0
        assert "resolved" in result.output.lower()

    @patch("src.config.profiles.load_profile")
    @patch("src.config.settings.get_active_profile_name")
    def test_unresolved_secrets(self, mock_profile_name, mock_load):
        mock_profile_name.return_value = "production"
        mock_profile = MagicMock()
        mock_profile.settings.model_dump.return_value = {
            "anthropic_api_key": "${ANTHROPIC_API_KEY}",
        }
        mock_load.return_value = mock_profile

        with patch.dict("os.environ", {}, clear=False):
            # Ensure the env var is not set
            import os

            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = runner.invoke(app, ["manage", "check-profile-secrets"])
            # Should report unresolved
            assert "unresolved" in result.output.lower() or "ANTHROPIC_API_KEY" in result.output
