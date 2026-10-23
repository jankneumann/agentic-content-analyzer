from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


def _storage():
    from src.services import storage_governance

    return storage_governance


def test_default_allocations_fit_one_terabyte_with_required_reserve() -> None:
    storage = _storage()

    allocation = storage.StorageAllocation.default()

    assert allocation.component_total_percent == 87
    assert allocation.reserve_percent == 13
    allocation.validate()


@pytest.mark.parametrize(
    ("component", "limit"),
    [
        ("application_postgresql", 22),
        ("falkordb", 12),
        ("clickhouse", 28),
        ("minio", 8),
        ("backups", 15),
        ("redis_and_logs", 2),
    ],
)
def test_component_allocations_cannot_exceed_approved_maximum(
    component: str,
    limit: int,
) -> None:
    storage = _storage()
    values = dict(storage.DEFAULT_COMPONENT_BUDGETS_PERCENT)
    values[component] = limit + 1

    with pytest.raises(ValueError, match=component):
        storage.StorageAllocation(values, reserve_percent=13).validate()


def test_allocations_cannot_consume_required_host_reserve() -> None:
    storage = _storage()

    with pytest.raises(ValueError, match="reserve"):
        storage.StorageAllocation(
            dict(storage.DEFAULT_COMPONENT_BUDGETS_PERCENT), reserve_percent=12
        ).validate()


def test_high_watermark_halves_ingestion_and_suppresses_success_detail() -> None:
    storage = _storage()
    controller = storage.StorageController()

    decision = controller.evaluate(
        usage_percent=80,
        scheduled_ingestion_concurrency=9,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        operation_id="101",
        trace_id="1" * 32,
    )

    assert decision.state is storage.StorageState.HIGH
    assert decision.scheduled_ingestion_concurrency == 4
    assert decision.suppress_success_excerpts is True
    assert decision.pause_nonessential_ingestion is False
    assert decision.run_supported_cleanup is True
    assert decision.alert is None


def test_high_watermark_concurrency_has_a_minimum_of_one() -> None:
    storage = _storage()

    decision = storage.StorageController().evaluate(
        usage_percent=80,
        scheduled_ingestion_concurrency=1,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        operation_id="101",
        trace_id="1" * 32,
    )

    assert decision.scheduled_ingestion_concurrency == 1


def test_critical_watermark_pauses_only_nonessential_ingestion() -> None:
    storage = _storage()

    decision = storage.StorageController().evaluate(
        usage_percent=90,
        scheduled_ingestion_concurrency=8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        operation_id="102",
        trace_id="2" * 32,
    )

    assert decision.state is storage.StorageState.CRITICAL
    assert decision.scheduled_ingestion_concurrency == 0
    assert decision.pause_nonessential_ingestion is True
    assert set(decision.allowed_operation_classes) == {
        "safety",
        "cleanup",
        "alert",
        "restore",
    }
    assert decision.alert is not None
    assert decision.alert.operation_id == "102"
    assert decision.alert.trace_id == "2" * 32
    assert decision.alert.stage == "alert"


def test_high_state_clears_only_after_fifteen_sustained_minutes_at_75() -> None:
    storage = _storage()
    controller = storage.StorageController()
    start = datetime(2026, 8, 29, tzinfo=UTC)
    kwargs = {"scheduled_ingestion_concurrency": 8, "operation_id": "1", "trace_id": "a" * 32}

    controller.evaluate(usage_percent=80, now=start, **kwargs)
    before = controller.evaluate(usage_percent=75, now=start + timedelta(minutes=1), **kwargs)
    almost = controller.evaluate(
        usage_percent=75, now=start + timedelta(minutes=15, seconds=59), **kwargs
    )
    cleared = controller.evaluate(usage_percent=75, now=start + timedelta(minutes=16), **kwargs)

    assert before.state is storage.StorageState.HIGH
    assert almost.state is storage.StorageState.HIGH
    assert cleared.state is storage.StorageState.NORMAL


def test_high_hysteresis_timer_resets_when_usage_rises_above_75() -> None:
    storage = _storage()
    controller = storage.StorageController()
    start = datetime(2026, 8, 29, tzinfo=UTC)
    kwargs = {"scheduled_ingestion_concurrency": 4, "operation_id": "1", "trace_id": "a" * 32}

    controller.evaluate(usage_percent=80, now=start, **kwargs)
    controller.evaluate(usage_percent=75, now=start + timedelta(minutes=1), **kwargs)
    controller.evaluate(usage_percent=76, now=start + timedelta(minutes=10), **kwargs)
    decision = controller.evaluate(usage_percent=75, now=start + timedelta(minutes=20), **kwargs)

    assert decision.state is storage.StorageState.HIGH


def test_critical_state_degrades_to_high_only_after_fifteen_minutes_at_85() -> None:
    storage = _storage()
    controller = storage.StorageController()
    start = datetime(2026, 8, 29, tzinfo=UTC)
    kwargs = {"scheduled_ingestion_concurrency": 4, "operation_id": "1", "trace_id": "a" * 32}

    controller.evaluate(usage_percent=90, now=start, **kwargs)
    controller.evaluate(usage_percent=85, now=start + timedelta(minutes=1), **kwargs)
    decision = controller.evaluate(usage_percent=85, now=start + timedelta(minutes=16), **kwargs)

    assert decision.state is storage.StorageState.HIGH
    assert decision.pause_nonessential_ingestion is False
    assert decision.suppress_success_excerpts is True


@pytest.mark.parametrize("state_usage", [80, 90])
def test_cleanup_failure_preserves_current_state_and_emits_correlated_alert(
    state_usage: int,
) -> None:
    storage = _storage()
    controller = storage.StorageController()
    now = datetime(2026, 8, 29, tzinfo=UTC)

    entered = controller.evaluate(
        usage_percent=state_usage,
        scheduled_ingestion_concurrency=4,
        now=now,
        operation_id="303",
        trace_id="3" * 32,
    )
    failed = controller.record_cleanup(
        storage.CleanupResult.failed("supported_cleanup_timeout"),
        operation_id="303",
        trace_id="3" * 32,
    )

    assert failed.state is entered.state
    assert failed.alert is not None
    assert failed.alert.operation_id == "303"
    assert failed.alert.trace_id == "3" * 32
    assert failed.alert.diagnostic_code == "supported_cleanup_timeout"
    assert failed.alert.outcome == "retryable_failure"


def test_supported_outcome_specific_retention_prioritizes_failure_evidence() -> None:
    storage = _storage()

    plan = storage.plan_retention(
        storage.RetentionCapabilities(outcome_specific_deletion=True),
        successful_days=30,
        failed_days=90,
        high_watermark_persists=True,
    )

    assert plan.successful_trace_days == 30
    assert plan.failed_trace_days == 90
    assert plan.failed_attempt_days == 90
    assert plan.pause_nonessential_ingestion is False
    assert plan.delete_failure_evidence is False
    assert plan.modify_langfuse_owned_schema is False


def test_limited_retention_capability_keeps_all_traces_for_90_days() -> None:
    storage = _storage()

    plan = storage.plan_retention(
        storage.RetentionCapabilities(outcome_specific_deletion=False),
        successful_days=30,
        failed_days=90,
        high_watermark_persists=False,
    )

    assert plan.successful_trace_days == 90
    assert plan.failed_trace_days == 90
    assert plan.mode == "retain_all_to_failure_window"
    assert plan.pause_nonessential_ingestion is False


def test_limited_retention_pauses_before_deleting_failure_evidence() -> None:
    storage = _storage()

    plan = storage.plan_retention(
        storage.RetentionCapabilities(outcome_specific_deletion=False),
        successful_days=30,
        failed_days=90,
        high_watermark_persists=True,
    )

    assert plan.pause_nonessential_ingestion is True
    assert plan.delete_failure_evidence is False
    assert plan.modify_langfuse_owned_schema is False


@pytest.mark.parametrize("usage", [-1, 101])
def test_usage_percent_is_bounded(usage: int) -> None:
    storage = _storage()

    with pytest.raises(ValueError, match="usage_percent"):
        storage.StorageController().evaluate(
            usage_percent=usage,
            scheduled_ingestion_concurrency=4,
            now=datetime(2026, 8, 29, tzinfo=UTC),
            operation_id="1",
            trace_id="a" * 32,
        )
