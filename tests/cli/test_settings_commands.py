"""Tests for settings CLI commands."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.models.settings_override import SettingsOverride

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_db():
    """Mock database for CLI tests.

    CLI commands use lazy imports (from X import Y inside function body),
    so we must patch at the SOURCE module, not the consumer module.
    """
    mock_session = MagicMock()

    @contextmanager
    def mock_get_db():
        yield mock_session

    with patch("src.storage.database.get_db", mock_get_db):
        yield mock_session


class TestSettingsList:
    """Tests for aca settings list."""

    def test_list_empty(self, mock_db):
        with patch("src.services.settings_service.SettingsService.list_by_prefix", return_value=[]):
            result = runner.invoke(app, ["settings", "list"])
            assert result.exit_code == 0
            assert "No settings overrides found" in result.output

    def test_list_with_data(self, mock_db):
        overrides = [
            {
                "key": "model.summarization",
                "value": "claude-haiku-4-5",
                "version": 1,
                "description": None,
            },
            {
                "key": "voice.provider",
                "value": "openai",
                "version": 2,
                "description": "Changed to openai",
            },
        ]
        with patch(
            "src.services.settings_service.SettingsService.list_by_prefix", return_value=overrides
        ):
            result = runner.invoke(app, ["settings", "list"])
            assert result.exit_code == 0
            assert "model.summarization" in result.output
            assert "voice.provider" in result.output
            assert "Total: 2 override(s)" in result.output

    def test_list_with_prefix(self, mock_db):
        with patch(
            "src.services.settings_service.SettingsService.list_by_prefix", return_value=[]
        ) as mock_list:
            result = runner.invoke(app, ["settings", "list", "--prefix", "model"])
            assert result.exit_code == 0
            mock_list.assert_called_once_with("model")


class TestSettingsGet:
    """Tests for aca settings get."""

    def test_get_existing(self, mock_db):
        mock_override = MagicMock(spec=SettingsOverride)
        mock_override.key = "model.summarization"
        mock_override.value = "claude-haiku-4-5"
        mock_override.version = 1
        mock_override.description = "Cost savings"

        with patch(
            "src.services.settings_service.SettingsService.get_override", return_value=mock_override
        ):
            result = runner.invoke(app, ["settings", "get", "model.summarization"])
            assert result.exit_code == 0
            assert "claude-haiku-4-5" in result.output
            assert "Cost savings" in result.output

    def test_get_nonexistent(self, mock_db):
        with patch("src.services.settings_service.SettingsService.get_override", return_value=None):
            result = runner.invoke(app, ["settings", "get", "model.nonexistent"])
            assert result.exit_code == 0
            assert "No override set" in result.output


class TestSettingsSet:
    """Tests for aca settings set."""

    def test_set_value(self, mock_db):
        mock_override = MagicMock(spec=SettingsOverride)
        mock_override.version = 1

        with (
            patch("src.services.settings_service.SettingsService.set") as mock_set,
            patch(
                "src.services.settings_service.SettingsService.get_override",
                return_value=mock_override,
            ),
        ):
            result = runner.invoke(
                app, ["settings", "set", "model.summarization", "claude-sonnet-4-5"]
            )
            assert result.exit_code == 0
            assert "Set model.summarization = claude-sonnet-4-5" in result.output
            mock_set.assert_called_once()

    def test_set_with_description(self, mock_db):
        mock_override = MagicMock(spec=SettingsOverride)
        mock_override.version = 1

        with (
            patch("src.services.settings_service.SettingsService.set") as mock_set,
            patch(
                "src.services.settings_service.SettingsService.get_override",
                return_value=mock_override,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "settings",
                    "set",
                    "model.summarization",
                    "claude-sonnet-4-5",
                    "--description",
                    "Quality improvement",
                ],
            )
            assert result.exit_code == 0
            mock_set.assert_called_once_with(
                "model.summarization", "claude-sonnet-4-5", description="Quality improvement"
            )


class TestSettingsReset:
    """Tests for aca settings reset."""

    def test_reset_existing(self, mock_db):
        with patch("src.services.settings_service.SettingsService.delete", return_value=True):
            result = runner.invoke(app, ["settings", "reset", "model.summarization"])
            assert result.exit_code == 0
            assert "Reset" in result.output

    def test_reset_nonexistent(self, mock_db):
        with patch("src.services.settings_service.SettingsService.delete", return_value=False):
            result = runner.invoke(app, ["settings", "reset", "model.nonexistent"])
            assert result.exit_code == 0
            assert "No override found" in result.output
