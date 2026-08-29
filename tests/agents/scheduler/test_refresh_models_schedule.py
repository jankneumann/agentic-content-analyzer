"""Test the model-registry refresh schedule entry (model-registry-freshness)."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.agents.scheduler.scheduler import AgentScheduler

SCHEDULE_PATH = "settings/schedule.yaml"
# 2025-06-16 is a Monday; refresh_models cron is "0 4 * * 1".
MONDAY_0400 = datetime(2025, 6, 16, 4, 0)


def _scheduler(enqueue_fn=None) -> AgentScheduler:
    sched = AgentScheduler(schedule_path=SCHEDULE_PATH, enqueue_fn=enqueue_fn)
    sched.load_schedules()
    return sched


def test_refresh_models_entry_present_and_disabled_by_default():
    sched = _scheduler()
    entry = sched._schedules.get("refresh_models")
    assert entry is not None
    assert entry.task_type == "maintenance"
    assert entry.params.get("actions") == ["refresh_models"]
    # Safe default (Rule 4): opt-in.
    assert entry.enabled is False


@pytest.mark.asyncio
async def test_enqueues_once_per_minute_when_enabled():
    enqueue_fn = AsyncMock(return_value="task-models")
    sched = _scheduler(enqueue_fn=enqueue_fn)
    sched.start()  # start() reloads schedules from disk
    sched.enable_schedule("refresh_models")  # enable after start so it sticks

    await sched.tick(MONDAY_0400)
    # Same minute again -> dedup guard must prevent a second enqueue.
    await sched.tick(MONDAY_0400)

    refresh_payloads = [
        c.args[0] for c in enqueue_fn.call_args_list if c.args[0]["schedule_id"] == "refresh_models"
    ]
    assert len(refresh_payloads) == 1  # enqueued exactly once across both ticks
    payload = refresh_payloads[0]
    assert payload["task_type"] == "maintenance"
    assert payload["source"] == "schedule"
    assert payload["params"]["actions"] == ["refresh_models"]
