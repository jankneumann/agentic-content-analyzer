"""Tests for the agent CLI commands.

Uses Typer's CliRunner for testing command invocation,
argument parsing, and output formatting. DB service calls
are mocked to avoid requiring a live database.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.agent_commands import app

runner = CliRunner()

# A reusable fake task object for mocking
_FAKE_TASK_ID = uuid.uuid4()


def _make_fake_task(**overrides):
    """Create a mock AgentTask with sensible defaults."""
    task = MagicMock()
    task.id = overrides.get("id", _FAKE_TASK_ID)
    task.task_type = overrides.get("task_type", "research")
    task.status = overrides.get("status", "received")
    task.persona_name = overrides.get("persona_name", "default")
    task.prompt = overrides.get("prompt", "Test prompt")
    task.result = overrides.get("result")
    task.error_message = overrides.get("error_message")
    task.created_at = overrides.get("created_at", datetime.now(UTC))
    task.started_at = overrides.get("started_at")
    task.completed_at = overrides.get("completed_at")
    task.cost_total = overrides.get("cost_total")
    task.tokens_total = overrides.get("tokens_total")
    return task


def _make_fake_insight(**overrides):
    """Create a mock AgentInsight."""
    insight = MagicMock()
    insight.id = overrides.get("id", uuid.uuid4())
    insight.insight_type = overrides.get("insight_type", "trend")
    insight.title = overrides.get("title", "Test Insight")
    insight.content = overrides.get("content", "Some insight content")
    insight.confidence = overrides.get("confidence", 0.85)
    insight.created_at = overrides.get("created_at", datetime.now(UTC))
    return insight


# ============================================================================
# Task commands
# ============================================================================


class TestTaskCommand:
    """Test the 'agent task' command."""

    @patch("src.cli.agent_commands.get_db")
    def test_submit_task(self, mock_get_db):
        fake_task = _make_fake_task()
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.create_task.return_value = fake_task
            result = runner.invoke(app, ["task", "What are the trends in AI agents?"])

        assert result.exit_code == 0
        assert "Task submitted" in result.output

    @patch("src.cli.agent_commands.get_db")
    def test_submit_task_with_persona(self, mock_get_db):
        fake_task = _make_fake_task(persona_name="ai-ml-technology")
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.create_task.return_value = fake_task
            result = runner.invoke(
                app,
                ["task", "Analyze AI trends", "--persona", "ai-ml-technology"],
            )

        assert result.exit_code == 0
        assert "ai-ml-technology" in result.output

    @patch("src.cli.agent_commands.get_db")
    def test_submit_task_with_type(self, mock_get_db):
        fake_task = _make_fake_task(task_type="analysis")
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.create_task.return_value = fake_task
            result = runner.invoke(
                app,
                ["task", "Run analysis", "--type", "analysis"],
            )

        assert result.exit_code == 0
        assert "analysis" in result.output

    @patch("src.cli.agent_commands.get_db")
    def test_submit_task_with_output(self, mock_get_db):
        fake_task = _make_fake_task()
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.create_task.return_value = fake_task
            result = runner.invoke(
                app,
                ["task", "Generate report", "--output", "technical_report"],
            )

        assert result.exit_code == 0

    @patch("src.cli.agent_commands.get_db")
    def test_submit_task_with_sources(self, mock_get_db):
        fake_task = _make_fake_task()
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.create_task.return_value = fake_task
            result = runner.invoke(
                app,
                ["task", "Check papers", "--sources", "arxiv,scholar"],
            )

        assert result.exit_code == 0


# ============================================================================
# Status command
# ============================================================================


class TestStatusCommand:
    """Test the 'agent status' command."""

    @patch("src.cli.agent_commands.get_db")
    def test_status_no_id(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.list_tasks.return_value = ([], 0)
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0

    @patch("src.cli.agent_commands.get_db")
    def test_status_with_id(self, mock_get_db):
        fake_task = _make_fake_task(prompt="Test prompt")
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        task_id = str(uuid.uuid4())
        with patch("src.cli.agent_commands.AgentTaskService") as mock_svc_cls:
            mock_svc_cls.return_value.get_task.return_value = fake_task
            result = runner.invoke(app, ["status", task_id])

        assert result.exit_code == 0


# ============================================================================
# Insights command
# ============================================================================


class TestInsightsCommand:
    """Test the 'agent insights' command."""

    @patch("src.cli.agent_commands.get_db")
    def test_list_insights(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentInsightService") as mock_svc_cls:
            mock_svc_cls.return_value.list_insights.return_value = ([], 0)
            result = runner.invoke(app, ["insights"])

        assert result.exit_code == 0

    @patch("src.cli.agent_commands.get_db")
    def test_list_insights_with_type(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentInsightService") as mock_svc_cls:
            mock_svc_cls.return_value.list_insights.return_value = ([], 0)
            result = runner.invoke(app, ["insights", "--type", "trend"])

        assert result.exit_code == 0

    @patch("src.cli.agent_commands.get_db")
    def test_list_insights_with_since(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.cli.agent_commands.AgentInsightService") as mock_svc_cls:
            mock_svc_cls.return_value.list_insights.return_value = ([], 0)
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

    @patch("src.cli.agent_commands.get_db")
    def test_approve(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_request = MagicMock()
        mock_request.status = "approved"

        request_id = str(uuid.uuid4())
        with patch("src.cli.agent_commands.ApprovalService") as mock_svc_cls:
            mock_svc_cls.return_value.decide_request.return_value = mock_request
            result = runner.invoke(app, ["approve", request_id])

        assert result.exit_code == 0
        assert "Approved" in result.output

    @patch("src.cli.agent_commands.get_db")
    def test_deny(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_request = MagicMock()
        mock_request.status = "denied"

        request_id = str(uuid.uuid4())
        with patch("src.cli.agent_commands.ApprovalService") as mock_svc_cls:
            mock_svc_cls.return_value.decide_request.return_value = mock_request
            result = runner.invoke(app, ["deny", request_id, "--reason", "Too broad"])

        assert result.exit_code == 0
        assert "Denied" in result.output

    def test_deny_requires_reason(self):
        result = runner.invoke(app, ["deny", "req-123"])
        assert result.exit_code != 0
