"""Tests for the root CLI app (app.py)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import _set_json_mode, is_json_mode, output_result

runner = CliRunner()


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "aca" in result.output

    def test_short_version_flag(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "aca" in result.output


class TestNoArgsHelp:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # Typer's no_args_is_help=True causes exit code 0 on some versions, 2 on others
        assert result.exit_code in (0, 2)
        assert "Agentic Content Aggregator" in result.output or "Usage" in result.output


class TestJsonMode:
    def test_json_mode_default_off(self):
        _set_json_mode(False)
        assert is_json_mode() is False

    def test_json_mode_set(self):
        _set_json_mode(True)
        assert is_json_mode() is True
        _set_json_mode(False)


class TestOutputResult:
    def test_output_result_string(self, capsys):
        _set_json_mode(False)
        output_result("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_output_result_string_json(self, capsys):
        _set_json_mode(True)
        output_result("hello")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["message"] == "hello"
        assert data["success"] is True
        _set_json_mode(False)

    def test_output_result_dict_json(self, capsys):
        _set_json_mode(True)
        output_result({"key": "value"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "value"
        _set_json_mode(False)


class TestSubcommandGroups:
    """Verify all expected subcommand groups are registered."""

    def test_ingest_group_exists(self):
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0

    def test_summarize_group_exists(self):
        result = runner.invoke(app, ["summarize", "--help"])
        assert result.exit_code == 0

    def test_create_digest_group_exists(self):
        result = runner.invoke(app, ["create-digest", "--help"])
        assert result.exit_code == 0

    def test_pipeline_group_exists(self):
        result = runner.invoke(app, ["pipeline", "--help"])
        assert result.exit_code == 0

    def test_review_group_exists(self):
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0

    def test_analyze_group_exists(self):
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0

    def test_graph_group_exists(self):
        result = runner.invoke(app, ["graph", "--help"])
        assert result.exit_code == 0

    def test_podcast_group_exists(self):
        result = runner.invoke(app, ["podcast", "--help"])
        assert result.exit_code == 0

    def test_manage_group_exists(self):
        result = runner.invoke(app, ["manage", "--help"])
        assert result.exit_code == 0

    def test_profile_group_exists(self):
        result = runner.invoke(app, ["profile", "--help"])
        assert result.exit_code == 0
