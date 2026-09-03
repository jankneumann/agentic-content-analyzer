"""GX-10 storage budgets, watermarks, hysteresis, and retention decisions.

This module deliberately returns policy decisions instead of deleting anything.
Callers may execute only supported application/service cleanup APIs and then feed
the bounded result back through :meth:`StorageController.record_cleanup`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

DEFAULT_COMPONENT_BUDGETS_PERCENT: Mapping[str, int] = MappingProxyType(
    {
        "application_postgresql": 22,
        "falkordb": 12,
        "clickhouse": 28,
        "minio": 8,
        "backups": 15,
        "redis_and_logs": 2,
    }
)


@dataclass(frozen=True, slots=True)
class StorageAllocation:
    """Logical component maxima plus the host reserve."""

    component_budgets_percent: Mapping[str, int]
    reserve_percent: int

    @classmethod
    def default(cls) -> StorageAllocation:
        return cls(dict(DEFAULT_COMPONENT_BUDGETS_PERCENT), reserve_percent=13)

    @property
    def component_total_percent(self) -> int:
        return sum(self.component_budgets_percent.values())

    def validate(self) -> None:
        if set(self.component_budgets_percent) != set(DEFAULT_COMPONENT_BUDGETS_PERCENT):
            raise ValueError("component budgets must name the complete GX-10 allocation")
        for component, maximum in DEFAULT_COMPONENT_BUDGETS_PERCENT.items():
            value = self.component_budgets_percent[component]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{component} budget must be a non-negative integer")
            if value > maximum:
                raise ValueError(f"{component} budget exceeds its approved maximum")
        if self.reserve_percent < 13:
            raise ValueError("reserve must be at least 13 percent")
        if self.component_total_percent + self.reserve_percent > 100:
            raise ValueError("component budgets plus reserve exceed the managed filesystem")


class StorageState(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class StoragePolicy:
    high_watermark_percent: int = 80
    high_clear_percent: int = 75
    critical_watermark_percent: int = 90
    critical_clear_percent: int = 85
    hysteresis: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if not (
            0
            <= self.high_clear_percent
            < self.high_watermark_percent
            < self.critical_clear_percent
            < self.critical_watermark_percent
            <= 100
        ):
            raise ValueError("watermarks must preserve clear/high/clear/critical ordering")
        if self.hysteresis <= timedelta(0):
            raise ValueError("hysteresis must be positive")


@dataclass(frozen=True, slots=True)
class CorrelatedStorageAlert:
    operation_id: str
    trace_id: str
    stage: str
    outcome: str
    diagnostic_code: str


@dataclass(frozen=True, slots=True)
class StorageDecision:
    state: StorageState
    scheduled_ingestion_concurrency: int
    suppress_success_excerpts: bool
    pause_nonessential_ingestion: bool
    run_supported_cleanup: bool
    allowed_operation_classes: tuple[str, ...]
    alert: CorrelatedStorageAlert | None = None


@dataclass(frozen=True, slots=True)
class CleanupResult:
    succeeded: bool
    diagnostic_code: str | None = None

    @classmethod
    def successful(cls) -> CleanupResult:
        return cls(True)

    @classmethod
    def failed(cls, diagnostic_code: str) -> CleanupResult:
        if not diagnostic_code or len(diagnostic_code) > 100:
            raise ValueError("diagnostic_code must contain 1-100 characters")
        return cls(False, diagnostic_code)


@dataclass(slots=True)
class StorageController:
    """Stateful watermark controller with sustained-time hysteresis."""

    policy: StoragePolicy = field(default_factory=StoragePolicy)
    state: StorageState = StorageState.NORMAL
    _clear_since: datetime | None = None

    @classmethod
    def from_state(cls, value: Mapping[str, object]) -> StorageController:
        """Restore only the bounded, versioned policy state needed for hysteresis."""
        if set(value) != {"schema_version", "state", "clear_since"}:
            raise ValueError("storage controller state has unexpected fields")
        if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
            raise ValueError("storage controller state schema is unsupported")
        try:
            state = StorageState(value["state"])
        except (TypeError, ValueError) as exc:
            raise ValueError("storage controller state is invalid") from exc
        clear_value = value["clear_since"]
        clear_since = None
        if clear_value is not None:
            if not isinstance(clear_value, str):
                raise ValueError("storage clear timestamp must be a string or null")
            try:
                clear_since = datetime.fromisoformat(clear_value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("storage clear timestamp is invalid") from exc
            if clear_since.tzinfo is None:
                raise ValueError("storage clear timestamp must include an offset")
            clear_since = clear_since.astimezone(UTC)
        if state is StorageState.NORMAL and clear_since is not None:
            raise ValueError("normal storage state cannot retain a clear timer")
        return cls(state=state, _clear_since=clear_since)

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "state": str(self.state),
            "clear_since": (
                self._clear_since.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if self._clear_since is not None
                else None
            ),
        }

    def evaluate(
        self,
        *,
        usage_percent: int,
        scheduled_ingestion_concurrency: int,
        now: datetime,
        operation_id: str,
        trace_id: str,
    ) -> StorageDecision:
        if (
            not isinstance(usage_percent, int)
            or isinstance(usage_percent, bool)
            or not 0 <= usage_percent <= 100
        ):
            raise ValueError("usage_percent must be an integer from 0 through 100")
        if scheduled_ingestion_concurrency < 1:
            raise ValueError("scheduled_ingestion_concurrency must be positive")

        previous = self.state
        self._advance_state(usage_percent=usage_percent, now=now)
        alert = None
        if self.state is StorageState.CRITICAL and previous is not StorageState.CRITICAL:
            alert = _alert(
                operation_id,
                trace_id,
                diagnostic_code="storage_critical_watermark",
                outcome="permanent_failure",
            )
        return self._decision(
            scheduled_ingestion_concurrency=scheduled_ingestion_concurrency,
            alert=alert,
        )

    def _advance_state(self, *, usage_percent: int, now: datetime) -> None:
        if self.state is StorageState.NORMAL:
            if usage_percent >= self.policy.critical_watermark_percent:
                self._transition(StorageState.CRITICAL)
            elif usage_percent >= self.policy.high_watermark_percent:
                self._transition(StorageState.HIGH)
            return

        if self.state is StorageState.HIGH:
            if usage_percent >= self.policy.critical_watermark_percent:
                self._transition(StorageState.CRITICAL)
            elif usage_percent <= self.policy.high_clear_percent:
                if self._sustained(now):
                    self._transition(StorageState.NORMAL)
            else:
                self._clear_since = None
            return

        if usage_percent <= self.policy.critical_clear_percent:
            if self._sustained(now):
                self._transition(StorageState.HIGH)
        else:
            self._clear_since = None

    def _sustained(self, now: datetime) -> bool:
        if self._clear_since is None:
            self._clear_since = now
            return False
        return now - self._clear_since >= self.policy.hysteresis

    def _transition(self, state: StorageState) -> None:
        self.state = state
        self._clear_since = None

    def _decision(
        self,
        *,
        scheduled_ingestion_concurrency: int,
        alert: CorrelatedStorageAlert | None,
    ) -> StorageDecision:
        if self.state is StorageState.NORMAL:
            concurrency = scheduled_ingestion_concurrency
        elif self.state is StorageState.HIGH:
            concurrency = max(1, scheduled_ingestion_concurrency // 2)
        else:
            concurrency = 0
        return StorageDecision(
            state=self.state,
            scheduled_ingestion_concurrency=concurrency,
            suppress_success_excerpts=self.state is not StorageState.NORMAL,
            pause_nonessential_ingestion=self.state is StorageState.CRITICAL,
            run_supported_cleanup=self.state is not StorageState.NORMAL,
            allowed_operation_classes=("safety", "cleanup", "alert", "restore"),
            alert=alert,
        )

    def record_cleanup(
        self,
        result: CleanupResult,
        *,
        operation_id: str,
        trace_id: str,
    ) -> StorageDecision:
        """Record supported cleanup evidence without changing disk state itself."""
        alert = None
        if not result.succeeded:
            alert = _alert(
                operation_id,
                trace_id,
                diagnostic_code=result.diagnostic_code or "supported_cleanup_failed",
                outcome="retryable_failure",
            )
        return self._decision(scheduled_ingestion_concurrency=1, alert=alert)


def _alert(
    operation_id: str,
    trace_id: str,
    *,
    diagnostic_code: str,
    outcome: str,
) -> CorrelatedStorageAlert:
    return CorrelatedStorageAlert(
        operation_id=operation_id,
        trace_id=trace_id,
        stage="alert",
        outcome=outcome,
        diagnostic_code=diagnostic_code,
    )


@dataclass(frozen=True, slots=True)
class RetentionCapabilities:
    outcome_specific_deletion: bool


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    mode: str
    successful_trace_days: int
    failed_trace_days: int
    failed_attempt_days: int
    pause_nonessential_ingestion: bool
    delete_failure_evidence: bool = False
    modify_langfuse_owned_schema: bool = False


def plan_retention(
    capabilities: RetentionCapabilities,
    *,
    successful_days: int,
    failed_days: int,
    high_watermark_persists: bool,
) -> RetentionPlan:
    """Choose only supported cleanup, preserving failed evidence first."""
    if not 1 <= successful_days <= failed_days:
        raise ValueError("retention windows must be positive and failure-biased")
    if capabilities.outcome_specific_deletion:
        return RetentionPlan(
            mode="outcome_specific",
            successful_trace_days=successful_days,
            failed_trace_days=failed_days,
            failed_attempt_days=failed_days,
            pause_nonessential_ingestion=False,
        )
    return RetentionPlan(
        mode="retain_all_to_failure_window",
        successful_trace_days=failed_days,
        failed_trace_days=failed_days,
        failed_attempt_days=failed_days,
        pause_nonessential_ingestion=high_watermark_persists,
    )
