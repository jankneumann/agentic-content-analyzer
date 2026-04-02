"""Tests for the AgentScheduler and cron matching logic."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from src.agents.scheduler.scheduler import (
    AgentScheduler,
    ScheduleEntry,
    cron_matches,
)

# ============================================================================
# cron_matches tests
# ============================================================================


class TestCronMatches:
    """Test the cron expression matcher."""

    def test_exact_minute_hour(self):
        """Match exact minute and hour with wildcards."""
        dt = datetime(2025, 6, 15, 9, 0)  # Sunday 09:00
        assert cron_matches("0 9 * * *", dt) is True

    def test_exact_minute_hour_no_match(self):
        dt = datetime(2025, 6, 15, 10, 0)
        assert cron_matches("0 9 * * *", dt) is False

    def test_wildcard_all(self):
        dt = datetime(2025, 6, 15, 14, 33)
        assert cron_matches("* * * * *", dt) is True

    def test_interval_hour(self):
        """Match every 4 hours."""
        assert cron_matches("0 */4 * * *", datetime(2025, 6, 15, 0, 0)) is True
        assert cron_matches("0 */4 * * *", datetime(2025, 6, 15, 4, 0)) is True
        assert cron_matches("0 */4 * * *", datetime(2025, 6, 15, 8, 0)) is True
        assert cron_matches("0 */4 * * *", datetime(2025, 6, 15, 3, 0)) is False

    def test_interval_minute(self):
        """Match every 15 minutes."""
        assert cron_matches("*/15 * * * *", datetime(2025, 6, 15, 9, 0)) is True
        assert cron_matches("*/15 * * * *", datetime(2025, 6, 15, 9, 15)) is True
        assert cron_matches("*/15 * * * *", datetime(2025, 6, 15, 9, 30)) is True
        assert cron_matches("*/15 * * * *", datetime(2025, 6, 15, 9, 7)) is False

    def test_weekday_name(self):
        """Match specific weekday by name."""
        # 2025-06-16 is a Monday
        monday = datetime(2025, 6, 16, 10, 0)
        assert cron_matches("0 10 * * MON", monday) is True
        assert cron_matches("0 10 * * TUE", monday) is False

    def test_weekday_range(self):
        """Match weekday range MON-FRI."""
        monday = datetime(2025, 6, 16, 17, 0)  # Monday
        friday = datetime(2025, 6, 20, 17, 0)  # Friday
        saturday = datetime(2025, 6, 21, 17, 0)  # Saturday
        assert cron_matches("0 17 * * MON-FRI", monday) is True
        assert cron_matches("0 17 * * MON-FRI", friday) is True
        assert cron_matches("0 17 * * MON-FRI", saturday) is False

    def test_weekday_sunday(self):
        """Sunday is 0 in cron convention."""
        sunday = datetime(2025, 6, 15, 10, 0)  # Sunday
        assert cron_matches("0 10 * * SUN", sunday) is True
        assert cron_matches("0 10 * * 0", sunday) is True

    def test_comma_list(self):
        """Match comma-separated values."""
        assert cron_matches("0,30 * * * *", datetime(2025, 6, 15, 9, 0)) is True
        assert cron_matches("0,30 * * * *", datetime(2025, 6, 15, 9, 30)) is True
        assert cron_matches("0,30 * * * *", datetime(2025, 6, 15, 9, 15)) is False

    def test_numeric_range(self):
        """Match numeric ranges."""
        assert cron_matches("0 9-17 * * *", datetime(2025, 6, 15, 9, 0)) is True
        assert cron_matches("0 9-17 * * *", datetime(2025, 6, 15, 13, 0)) is True
        assert cron_matches("0 9-17 * * *", datetime(2025, 6, 15, 17, 0)) is True
        assert cron_matches("0 9-17 * * *", datetime(2025, 6, 15, 18, 0)) is False

    def test_day_of_month(self):
        """Match specific day of month."""
        assert cron_matches("0 0 1 * *", datetime(2025, 1, 1, 0, 0)) is True
        assert cron_matches("0 0 1 * *", datetime(2025, 1, 2, 0, 0)) is False

    def test_month(self):
        """Match specific month."""
        assert cron_matches("0 0 * 6 *", datetime(2025, 6, 15, 0, 0)) is True
        assert cron_matches("0 0 * 6 *", datetime(2025, 7, 15, 0, 0)) is False

    def test_invalid_cron_expression(self):
        """Invalid cron expressions return False."""
        assert cron_matches("bad", datetime(2025, 6, 15, 0, 0)) is False
        assert cron_matches("0 9 *", datetime(2025, 6, 15, 0, 0)) is False


# ============================================================================
# ScheduleEntry tests
# ============================================================================


class TestScheduleEntry:
    """Test the ScheduleEntry model."""

    def test_defaults(self):
        entry = ScheduleEntry(id="test", cron="0 9 * * *", task_type="analysis")
        assert entry.persona == "default"
        assert entry.enabled is True
        assert entry.priority == "medium"
        assert entry.params == {}
        assert entry.output is None
        assert entry.sources is None

    def test_full_config(self):
        entry = ScheduleEntry(
            id="trend",
            cron="0 9 * * MON",
            task_type="analysis",
            persona="ai-ml-technology",
            output="technical_report",
            sources=["arxiv", "scholar"],
            params={"lookback_days": 7},
            description="Weekly trend analysis",
            priority="high",
            enabled=False,
        )
        assert entry.persona == "ai-ml-technology"
        assert entry.sources == ["arxiv", "scholar"]
        assert entry.enabled is False


# ============================================================================
# AgentScheduler tests
# ============================================================================


class TestAgentScheduler:
    """Test the AgentScheduler class."""

    @pytest.fixture
    def schedule_yaml(self, tmp_path: Path) -> Path:
        """Create a temporary schedule YAML file."""
        schedule_data = {
            "schedules": {
                "morning_scan": {
                    "cron": "0 9 * * *",
                    "task_type": "analysis",
                    "persona": "ai-ml-technology",
                    "output": "technical_report",
                    "description": "Morning scan",
                    "priority": "medium",
                },
                "weekly_synthesis": {
                    "cron": "0 10 * * MON",
                    "task_type": "synthesis",
                    "persona": "leadership",
                    "output": "executive_briefing",
                    "description": "Weekly synthesis",
                    "priority": "medium",
                },
                "disabled_task": {
                    "cron": "0 12 * * *",
                    "task_type": "maintenance",
                    "description": "Disabled task",
                    "enabled": False,
                },
            }
        }
        yaml_path = tmp_path / "schedule.yaml"
        yaml_path.write_text(yaml.dump(schedule_data))
        return yaml_path

    def test_load_schedules(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()
        schedules = scheduler.list_schedules()
        assert len(schedules) == 3
        ids = {s.id for s in schedules}
        assert ids == {"morning_scan", "weekly_synthesis", "disabled_task"}

    def test_load_schedules_missing_file(self, tmp_path: Path):
        scheduler = AgentScheduler(schedule_path=str(tmp_path / "nonexistent.yaml"))
        scheduler.load_schedules()
        assert scheduler.list_schedules() == []

    def test_get_due_schedules_match(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        # 2025-06-16 09:00 is a Monday
        now = datetime(2025, 6, 16, 9, 0)
        due = scheduler.get_due_schedules(now)
        due_ids = {s.id for s in due}
        assert "morning_scan" in due_ids

    def test_get_due_schedules_weekday(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        # Monday at 10:00 should trigger weekly_synthesis
        monday_10 = datetime(2025, 6, 16, 10, 0)
        due = scheduler.get_due_schedules(monday_10)
        due_ids = {s.id for s in due}
        assert "weekly_synthesis" in due_ids

        # Tuesday at 10:00 should NOT trigger weekly_synthesis
        tuesday_10 = datetime(2025, 6, 17, 10, 0)
        due = scheduler.get_due_schedules(tuesday_10)
        due_ids = {s.id for s in due}
        assert "weekly_synthesis" not in due_ids

    def test_disabled_schedule_skipped(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        # 12:00 matches disabled_task's cron, but it's disabled
        now = datetime(2025, 6, 16, 12, 0)
        due = scheduler.get_due_schedules(now)
        due_ids = {s.id for s in due}
        assert "disabled_task" not in due_ids

    def test_deduplication_same_minute(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        now = datetime(2025, 6, 16, 9, 0)
        due1 = scheduler.get_due_schedules(now)
        assert len(due1) > 0

        # Simulate that tick ran
        scheduler._last_run["morning_scan"] = now

        # Same minute should not return it again
        due2 = scheduler.get_due_schedules(now)
        due2_ids = {s.id for s in due2}
        assert "morning_scan" not in due2_ids

    def test_deduplication_active_task(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        # Mark morning_scan as having an active task
        scheduler._active_tasks["morning_scan"] = "task-123"

        now = datetime(2025, 6, 16, 9, 0)
        due = scheduler.get_due_schedules(now)
        due_ids = {s.id for s in due}
        assert "morning_scan" not in due_ids

    def test_mark_task_completed(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        scheduler._active_tasks["morning_scan"] = "task-123"
        scheduler.mark_task_completed("morning_scan")
        assert "morning_scan" not in scheduler._active_tasks

    def test_enable_disable(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        assert scheduler.disable_schedule("morning_scan") is True
        entry = scheduler._schedules["morning_scan"]
        assert entry.enabled is False

        assert scheduler.enable_schedule("morning_scan") is True
        assert entry.enabled is True

        # Non-existent schedule
        assert scheduler.enable_schedule("nonexistent") is False
        assert scheduler.disable_schedule("nonexistent") is False

    @pytest.mark.asyncio
    async def test_tick_enqueues_tasks(self, schedule_yaml: Path):
        enqueue_fn = AsyncMock(return_value="task-abc")
        scheduler = AgentScheduler(
            schedule_path=str(schedule_yaml),
            enqueue_fn=enqueue_fn,
        )
        scheduler.start()

        now = datetime(2025, 6, 16, 9, 0)  # Monday 09:00
        task_ids = await scheduler.tick(now)

        assert len(task_ids) > 0
        assert "task-abc" in task_ids
        enqueue_fn.assert_called()

        # Verify payload structure
        call_args = enqueue_fn.call_args[0][0]
        assert call_args["task_type"] == "analysis"
        assert call_args["persona"] == "ai-ml-technology"
        assert call_args["source"] == "schedule"
        assert call_args["schedule_id"] == "morning_scan"

    @pytest.mark.asyncio
    async def test_tick_no_enqueue_fn(self, schedule_yaml: Path):
        scheduler = AgentScheduler(schedule_path=str(schedule_yaml))
        scheduler.load_schedules()

        now = datetime(2025, 6, 16, 9, 0)
        task_ids = await scheduler.tick(now)
        assert task_ids == []

    @pytest.mark.asyncio
    async def test_tick_enqueue_failure(self, schedule_yaml: Path):
        enqueue_fn = AsyncMock(side_effect=RuntimeError("queue down"))
        scheduler = AgentScheduler(
            schedule_path=str(schedule_yaml),
            enqueue_fn=enqueue_fn,
        )
        scheduler.load_schedules()

        now = datetime(2025, 6, 16, 9, 0)
        task_ids = await scheduler.tick(now)
        assert task_ids == []

    @pytest.mark.asyncio
    async def test_tick_no_due_schedules(self, schedule_yaml: Path):
        enqueue_fn = AsyncMock(return_value="task-xyz")
        scheduler = AgentScheduler(
            schedule_path=str(schedule_yaml),
            enqueue_fn=enqueue_fn,
        )
        scheduler.load_schedules()

        # 3 AM Tuesday — only disabled_task matches, but it's disabled
        now = datetime(2025, 6, 17, 3, 30)
        task_ids = await scheduler.tick(now)
        assert task_ids == []
        enqueue_fn.assert_not_called()
