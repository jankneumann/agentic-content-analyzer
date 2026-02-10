"""Tests for CLI prompt management commands.

Tests the `aca prompts` command group including:
- list, show, set, reset, export, import, test
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_prompt_cache():
    """Clear PromptService cache between tests."""
    from src.services.prompt_service import PromptService

    PromptService.clear_cache()
    yield
    PromptService.clear_cache()


@pytest.fixture()
def mock_db():
    """Create a mock database session with no overrides."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    return db


@pytest.fixture()
def mock_get_db(mock_db):
    """Patch get_db at the source module (lazy imports resolve there)."""

    @contextmanager
    def _get_db():
        yield mock_db

    with patch("src.storage.database.get_db", _get_db):
        yield mock_db


class TestListPrompts:
    """Tests for `aca prompts list`."""

    def test_list_prompts_shows_prompts(self, mock_get_db):
        """Test that list command shows prompts."""
        result = runner.invoke(app, ["prompts", "list"])

        assert result.exit_code == 0
        assert "PIPELINE" in result.output or "CHAT" in result.output
        assert "Total:" in result.output

    def test_list_prompts_with_category_filter(self, mock_get_db):
        """Test filtering by category."""
        result = runner.invoke(app, ["prompts", "list", "--category", "chat"])

        assert result.exit_code == 0
        assert "CHAT" in result.output
        # Should not show pipeline prompts
        assert "PIPELINE" not in result.output

    def test_list_prompts_json_output(self, mock_get_db):
        """Test JSON output mode."""
        result = runner.invoke(app, ["--json", "prompts", "list"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "prompts" in data
        assert "count" in data
        assert data["count"] > 0


class TestShowPrompt:
    """Tests for `aca prompts show`."""

    def test_show_existing_prompt(self, mock_get_db):
        """Test showing a prompt that exists."""
        result = runner.invoke(app, ["prompts", "show", "pipeline.summarization.system"])

        assert result.exit_code == 0
        assert "Key: pipeline.summarization.system" in result.output

    def test_show_nonexistent_prompt(self, mock_get_db):
        """Test showing a prompt that doesn't exist."""
        result = runner.invoke(app, ["prompts", "show", "pipeline.nonexistent.system"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_show_prompt_json_output(self, mock_get_db):
        """Test show in JSON mode."""
        result = runner.invoke(app, ["--json", "prompts", "show", "pipeline.summarization.system"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["key"] == "pipeline.summarization.system"
        assert "default_value" in data


class TestSetPrompt:
    """Tests for `aca prompts set`."""

    def test_set_prompt_with_value(self, mock_get_db):
        """Test setting a prompt override with inline value."""
        result = runner.invoke(
            app, ["prompts", "set", "chat.summary.system", "--value", "Custom prompt"]
        )

        assert result.exit_code == 0
        assert "Override set" in result.output

    def test_set_prompt_with_file(self, mock_get_db, tmp_path):
        """Test setting a prompt override from a file."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Custom prompt from file")

        result = runner.invoke(
            app, ["prompts", "set", "chat.summary.system", "--file", str(prompt_file)]
        )

        assert result.exit_code == 0
        assert "Override set" in result.output

    def test_set_prompt_requires_value_or_file(self, mock_get_db):
        """Test that set requires either --value or --file."""
        result = runner.invoke(app, ["prompts", "set", "chat.summary.system"])

        assert result.exit_code == 1
        assert "provide --value or --file" in result.output

    def test_set_prompt_rejects_both_value_and_file(self, mock_get_db, tmp_path):
        """Test that set rejects both --value and --file."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("test")

        result = runner.invoke(
            app,
            [
                "prompts",
                "set",
                "chat.summary.system",
                "--value",
                "inline",
                "--file",
                str(prompt_file),
            ],
        )

        assert result.exit_code == 1
        assert "not both" in result.output

    def test_set_nonexistent_prompt(self, mock_get_db):
        """Test setting a nonexistent prompt key."""
        result = runner.invoke(
            app, ["prompts", "set", "pipeline.nonexistent.system", "--value", "test"]
        )

        assert result.exit_code == 1
        assert "not found" in result.output


class TestResetPrompt:
    """Tests for `aca prompts reset`."""

    def test_reset_prompt(self, mock_get_db):
        """Test resetting a prompt override."""
        result = runner.invoke(app, ["prompts", "reset", "chat.summary.system"])

        assert result.exit_code == 0
        assert "Override cleared" in result.output


class TestExportPrompts:
    """Tests for `aca prompts export`."""

    def test_export_prompts(self, mock_get_db, tmp_path):
        """Test exporting prompts to YAML."""
        output_file = tmp_path / "export.yaml"

        result = runner.invoke(app, ["prompts", "export", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Exported" in result.output

        # Verify YAML structure
        import yaml

        data = yaml.safe_load(output_file.read_text())
        assert "pipeline" in data or "chat" in data


class TestImportPrompts:
    """Tests for `aca prompts import`."""

    def test_import_dry_run(self, mock_get_db, tmp_path):
        """Test dry run import."""
        import_file = tmp_path / "import.yaml"
        import_file.write_text("pipeline:\n  summarization:\n    system: 'Custom system prompt'\n")

        result = runner.invoke(app, ["prompts", "import", "--file", str(import_file), "--dry-run"])

        assert result.exit_code == 0
        assert "Would import" in result.output

    def test_import_nonexistent_file(self, mock_get_db):
        """Test importing from a file that doesn't exist."""
        result = runner.invoke(app, ["prompts", "import", "--file", "/nonexistent/file.yaml"])

        assert result.exit_code == 1
        assert "not found" in result.output


class TestTestPrompt:
    """Tests for `aca prompts test`."""

    def test_test_prompt_with_variables(self, mock_get_db):
        """Test rendering a prompt with variables."""
        result = runner.invoke(
            app,
            [
                "prompts",
                "test",
                "pipeline.podcast_script.length_brief",
                "--var",
                "period=daily",
            ],
        )

        assert result.exit_code == 0
        assert "daily" in result.output
        # Should not contain {period} placeholder
        assert "{period}" not in result.output

    def test_test_prompt_without_variables(self, mock_get_db):
        """Test rendering a prompt without providing variables."""
        result = runner.invoke(app, ["prompts", "test", "pipeline.podcast_script.length_brief"])

        assert result.exit_code == 0
        assert "Rendered prompt" in result.output

    def test_test_nonexistent_prompt(self, mock_get_db):
        """Test testing a nonexistent prompt."""
        result = runner.invoke(app, ["prompts", "test", "pipeline.nonexistent.system"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_test_prompt_invalid_variable_format(self, mock_get_db):
        """Test with an invalid variable format (missing =)."""
        result = runner.invoke(
            app,
            [
                "prompts",
                "test",
                "pipeline.podcast_script.length_brief",
                "--var",
                "bad_format",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid variable format" in result.output
