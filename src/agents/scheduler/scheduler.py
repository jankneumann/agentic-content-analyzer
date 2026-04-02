"""Schedule-driven proactive task engine.

Reads schedule.yaml, matches cron expressions against current time,
and enqueues agent_task jobs via a provided enqueue function. Uses
the existing PGQueuer job queue rather than introducing new scheduling
infrastructure.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Weekday name mapping for cron expressions
_WEEKDAY_MAP: dict[str, int] = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}


class ScheduleEntry(BaseModel):
    """A single schedule entry from schedule.yaml."""

    id: str
    cron: str
    task_type: str
    persona: str = "default"
    output: str | None = None
    sources: list[str] | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    priority: str = "medium"
    enabled: bool = True


def _parse_cron_field(field: str, value: int, max_value: int) -> bool:
    """Check if a single cron field matches a given value.

    Supports:
    - ``*`` — matches any value
    - ``5`` — exact match
    - ``*/N`` — interval (every N)
    - ``1,3,5`` — list
    - ``1-5`` — range
    - ``MON-FRI`` — weekday range (for weekday field only)
    - ``MON,WED`` — weekday list
    """
    if field == "*":
        return True

    # Handle comma-separated lists
    if "," in field:
        parts = [p.strip() for p in field.split(",")]
        return any(_parse_cron_field(p, value, max_value) for p in parts)

    # Handle ranges (e.g., "1-5" or "MON-FRI")
    range_match = re.match(r"^([A-Z]+|\d+)-([A-Z]+|\d+)$", field)
    if range_match:
        start_str, end_str = range_match.group(1), range_match.group(2)
        start = _WEEKDAY_MAP.get(start_str, None)
        end = _WEEKDAY_MAP.get(end_str, None)
        if start is None:
            start = int(start_str)
        if end is None:
            end = int(end_str)
        if start <= end:
            return start <= value <= end
        # Wrap around (e.g., FRI-MON means 5,6,0,1)
        return value >= start or value <= end

    # Handle intervals (e.g., "*/4")
    interval_match = re.match(r"^\*/(\d+)$", field)
    if interval_match:
        step = int(interval_match.group(1))
        return step > 0 and value % step == 0

    # Handle weekday names
    if field.upper() in _WEEKDAY_MAP:
        return _WEEKDAY_MAP[field.upper()] == value

    # Exact numeric match
    try:
        return int(field) == value
    except ValueError:
        logger.warning("Unrecognized cron field value: %s", field)
        return False


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    """Check if a cron expression matches the given datetime.

    Standard 5-field cron: ``minute hour day_of_month month day_of_week``

    Args:
        cron_expr: Cron expression string (e.g., ``"0 9 * * MON"``).
        dt: The datetime to check against.

    Returns:
        True if the cron expression matches the datetime.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        logger.error("Invalid cron expression (expected 5 fields): %s", cron_expr)
        return False

    minute, hour, day, month, weekday = parts

    # isoweekday: Mon=1..Sun=7; convert to cron convention: Sun=0..Sat=6
    cron_weekday = dt.isoweekday() % 7  # Mon=1, Sun=7 -> Sun=0, Mon=1, ..., Sat=6

    return (
        _parse_cron_field(minute, dt.minute, 59)
        and _parse_cron_field(hour, dt.hour, 23)
        and _parse_cron_field(day, dt.day, 31)
        and _parse_cron_field(month, dt.month, 12)
        and _parse_cron_field(weekday, cron_weekday, 6)
    )


class AgentScheduler:
    """Schedule-driven proactive task engine.

    Reads schedule.yaml, matches cron expressions against current time,
    and enqueues agent_task jobs via a provided enqueue function.
    """

    def __init__(
        self,
        schedule_path: str = "settings/schedule.yaml",
        enqueue_fn: Callable[[dict], Awaitable[str]] | None = None,
    ):
        self._schedule_path = schedule_path
        self._enqueue_fn = enqueue_fn
        self._schedules: dict[str, ScheduleEntry] = {}
        self._last_run: dict[str, datetime] = {}
        self._active_tasks: dict[str, str] = {}  # schedule_id -> task_id

    def load_schedules(self) -> None:
        """Load schedules from YAML file."""
        path = Path(self._schedule_path)
        if not path.exists():
            logger.warning("Schedule file not found: %s", self._schedule_path)
            return

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        schedules_data = data.get("schedules", {})
        self._schedules = {}

        for schedule_id, config in schedules_data.items():
            if not isinstance(config, dict):
                logger.warning("Skipping invalid schedule entry: %s", schedule_id)
                continue
            try:
                entry = ScheduleEntry(id=schedule_id, **config)
                self._schedules[schedule_id] = entry
            except Exception:
                logger.exception("Failed to parse schedule entry: %s", schedule_id)

        logger.info("Loaded %d schedules from %s", len(self._schedules), self._schedule_path)

    def get_due_schedules(self, now: datetime | None = None) -> list[ScheduleEntry]:
        """Return schedules whose cron matches the current time.

        Filters out disabled schedules and those that have already run
        in the current minute (deduplication).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        due: list[ScheduleEntry] = []
        for schedule_id, entry in self._schedules.items():
            if not entry.enabled:
                continue

            if not cron_matches(entry.cron, now):
                continue

            # Deduplication: skip if already ran in this minute
            last = self._last_run.get(schedule_id)
            if last and last.replace(second=0, microsecond=0) == now.replace(
                second=0, microsecond=0
            ):
                continue

            # Skip if previous run is still active
            if schedule_id in self._active_tasks:
                logger.debug(
                    "Skipping %s — previous run %s still active",
                    schedule_id,
                    self._active_tasks[schedule_id],
                )
                continue

            due.append(entry)

        return due

    async def tick(self, now: datetime | None = None) -> list[str]:
        """Check for due schedules and enqueue tasks.

        Returns:
            List of enqueued task IDs.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        due = self.get_due_schedules(now)
        if not due:
            return []

        enqueued: list[str] = []

        for entry in due:
            task_payload = {
                "schedule_id": entry.id,
                "task_type": entry.task_type,
                "persona": entry.persona,
                "output": entry.output,
                "sources": entry.sources,
                "params": entry.params,
                "priority": entry.priority,
                "source": "schedule",
            }

            if self._enqueue_fn is not None:
                try:
                    task_id = await self._enqueue_fn(task_payload)
                    self._last_run[entry.id] = now
                    self._active_tasks[entry.id] = task_id
                    enqueued.append(task_id)
                    logger.info(
                        "Enqueued schedule %s as task %s",
                        entry.id,
                        task_id,
                    )
                except Exception:
                    logger.exception("Failed to enqueue schedule %s", entry.id)
            else:
                logger.warning("No enqueue function set — skipping %s", entry.id)

        return enqueued

    def mark_task_completed(self, schedule_id: str) -> None:
        """Mark a scheduled task as completed, allowing re-enqueue."""
        self._active_tasks.pop(schedule_id, None)

    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule entry. Returns True if found."""
        entry = self._schedules.get(schedule_id)
        if entry is None:
            return False
        entry.enabled = True
        return True

    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule entry. Returns True if found."""
        entry = self._schedules.get(schedule_id)
        if entry is None:
            return False
        entry.enabled = False
        return True

    def list_schedules(self) -> list[ScheduleEntry]:
        """Return all loaded schedule entries."""
        return list(self._schedules.values())
