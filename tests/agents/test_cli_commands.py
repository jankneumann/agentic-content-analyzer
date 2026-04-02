"""Tests for the agent CLI commands.

Uses Typer's CliRunner for testing command invocation,
argument parsing, and output formatting.
"""

import pytest
from typer.testing import CliRunner

from src.cli.agent_commands import app

runner = CliRunner()


# ============================================================================
# Task commands
# ============================================================================


class TestTaskCommand:
    """Test the 'agent task' command."""

    def test_submit_task(self):
        result = runner.invoke(app, ["task", "What are the trends in AI agents?"])
        assert result.exit_code == 0
        assert "Task submitted" in result.output

    def test_submit_task_with_persona(self):
        result = runner.invoke(
            app,
            ["task", "Analyze AI trends", "--persona", "ai-ml-technology"],
        )
        assert result.exit_code == 0
        assert "ai-ml-technology" in result.output

    def test_submit_task_with_type(self):
        result = runner.invoke(
            app,
            ["task", "Run analysis", "--type", "analysis"],
        )
        assert result.exit_code == 0
        assert "analysis" in result.output

    def test_submit_task_with_output(self):
        result = runner.invoke(
            app,
            ["task", "Generate report", "--output", "technical_report"],
        )
        assert result.exit_code == 0
        assert "technical_report" in result.output

    def test_submit_task_with_sources(self):
        result = runner.invoke(
            app,
            ["task", "Check papers", "--sources", "arxiv,scholar"],
        )
        assert result.exit_code == 0
        assert "arxiv,scholar" in result.output


# ============================================================================
# Status command
# ============================================================================


class TestStatusCommand:
    """Test the 'agent status' command."""

    def test_status_no_id(self):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_status_with_id(self):
        result = runner.invoke(app, ["status", "abc-123"])
        assert result.exit_code == 0
        assert "abc-123" in result.output


# ============================================================================
# Insights command
# ============================================================================


class TestInsightsCommand:
    """Test the 'agent insights' command."""

    def test_list_insights(self):
        result = runner.invoke(app, ["insights"])
        assert result.exit_code == 0

    def test_list_insights_with_type(self):
        result = runner.invoke(app, ["insights", "--type", "trend"])
        assert result.exit_code == 0

    def test_list_insights_with_since(self):
        result = runner.invoke(app, ["insights", "--since", "2025-01-01"])
        assert result.exit_code == 0


# ============================================================================
# Personas command
# ============================================================================


class TestPersonasCommand:
    """Test the 'agent personas' command."""

    def test_list_personas(self):
        result = runner.invoke(app, ["personas"])
        assert result.exit_code == 0


# ============================================================================
# Schedule command
# ============================================================================


class TestScheduleCommand:
    """Test the 'agent schedule' command."""

    def test_list_schedules(self):
        result = runner.invoke(app, ["schedule"])
        assert result.exit_code == 0

    def test_enable_schedule(self):
        result = runner.invoke(app, ["schedule", "--enable", "morning_scan"])
        assert result.exit_code == 0

    def test_disable_schedule(self):
        result = runner.invoke(app, ["schedule", "--disable", "morning_scan"])
        assert result.exit_code == 0

    def test_enable_nonexistent(self):
        result = runner.invoke(app, ["schedule", "--enable", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output


# ============================================================================
# Approval commands
# ============================================================================


class TestApprovalCommands:
    """Test the 'agent approve' and 'agent deny' commands."""

    def test_approve(self):
        result = runner.invoke(app, ["approve", "req-123"])
        assert result.exit_code == 0
        assert "Approved" in result.output

    def test_deny(self):
        result = runner.invoke(app, ["deny", "req-123", "--reason", "Too broad"])
        assert result.exit_code == 0
        assert "Denied" in result.output

    def test_deny_requires_reason(self):
        result = runner.invoke(app, ["deny", "req-123"])
        assert result.exit_code != 0
