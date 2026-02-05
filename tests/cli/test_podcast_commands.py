"""Tests for podcast CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestPodcastGenerate:
    @patch("src.cli.adapters.generate_podcast_script_sync")
    def test_generate_success(self, mock_generate):
        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.title = "AI Weekly Podcast"
        mock_record.length = "standard"
        mock_record.word_count = 2500
        mock_record.status = "completed"
        mock_generate.return_value = mock_record

        result = runner.invoke(
            app,
            [
                "podcast",
                "generate",
                "--digest-id",
                "42",
            ],
        )
        assert result.exit_code == 0
        assert "Podcast script generated" in result.output
        assert "AI Weekly Podcast" in result.output

    @patch("src.cli.adapters.generate_podcast_script_sync")
    def test_generate_with_length(self, mock_generate):
        mock_record = MagicMock()
        mock_record.id = 2
        mock_record.title = "Brief Podcast"
        mock_record.length = "brief"
        mock_record.word_count = 800
        mock_record.status = "completed"
        mock_generate.return_value = mock_record

        result = runner.invoke(
            app,
            [
                "podcast",
                "generate",
                "--digest-id",
                "42",
                "--length",
                "brief",
            ],
        )
        assert result.exit_code == 0

    def test_generate_invalid_length(self):
        result = runner.invoke(
            app,
            [
                "podcast",
                "generate",
                "--digest-id",
                "42",
                "--length",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid length" in result.output or "Error" in result.output

    @patch("src.cli.adapters.generate_podcast_script_sync")
    def test_generate_failure(self, mock_generate):
        mock_generate.side_effect = RuntimeError("Generation failed")

        result = runner.invoke(app, ["podcast", "generate", "--digest-id", "42"])
        assert result.exit_code == 1


class TestPodcastListScripts:
    @patch("src.storage.database.get_db")
    def test_list_scripts_success(self, mock_get_db):
        mock_script = MagicMock()
        mock_script.id = 1
        mock_script.digest_id = 42
        mock_script.title = "AI Podcast #1"
        mock_script.length = "standard"
        mock_script.word_count = 2000
        mock_script.status = "completed"
        mock_script.created_at = MagicMock()
        mock_script.created_at.strftime.return_value = "2025-01-01 12:00"

        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_script
        ]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["podcast", "list-scripts"])
        assert result.exit_code == 0

    @patch("src.storage.database.get_db")
    def test_list_scripts_empty(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["podcast", "list-scripts"])
        assert result.exit_code == 0
        assert "No podcast scripts found" in result.output

    @patch("src.storage.database.get_db")
    def test_list_scripts_db_error(self, mock_get_db):
        mock_get_db.side_effect = RuntimeError("DB error")

        result = runner.invoke(app, ["podcast", "list-scripts"])
        assert result.exit_code == 1
