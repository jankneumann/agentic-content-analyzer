"""Freshness evaluation, check-window keying, and worker-loop emission.

The theme of this file is design A13's generalised lesson: a document describing a
constraint is not the code enforcing it. So nothing here asserts a regex in
isolation — every widening point is exercised by constructing a real envelope or
by driving the real emission path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from src.services.backup import manifest_reader
from src.services.backup.manifest_reader import BackupFreshnessStatus, read_freshness
from src.services.backup_freshness_alert import (
    MIN_WINDOW_SECONDS,
    check_window_start,
    emit_backup_freshness_alert,
    event_key_for,
    window_seconds_for,
)

NOW = datetime(2026, 8, 21, 4, 0, tzinfo=UTC)


def settings(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "environment": "production",
        "backup_monitoring_enabled": True,
        "backup_staleness_hours": 48,
        "backup_s3_bucket": "aca-backups",
        "backup_s3_prefix": "aca",
        "backup_s3_endpoint": None,
        "backup_s3_region": "auto",
        "backup_s3_access_key_id": None,
        "backup_s3_secret_access_key": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def manifest(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "environment": "production",
        "started_at": "2026-08-21T03:00:00Z",
        "completed_at": "2026-08-21T03:04:00Z",
        "overall_outcome": "succeeded",
        "retention_tier": "daily",
        "stores": [{"store": "postgres", "outcome": "succeeded", "required": True}],
    }
    base.update(overrides)
    return base


def evaluate(document: Any, cfg: Any = None, *, now: datetime = NOW) -> Any:
    manifest_reader.reset_cache()
    with patch.object(manifest_reader, "_fetch_manifest", lambda _s: document):
        return read_freshness(cfg or settings(), now=now, use_cache=False)


# --------------------------------------------------------------------- freshness


class TestManifestDerivedFreshness:
    def test_a_recent_complete_run_is_ok(self) -> None:
        assert evaluate(manifest()).status is BackupFreshnessStatus.OK

    def test_a_run_older_than_the_threshold_is_stale(self) -> None:
        old = manifest(completed_at="2026-08-18T03:00:00Z")
        assert evaluate(old).status is BackupFreshnessStatus.STALE

    def test_the_threshold_is_backup_staleness_hours(self) -> None:
        """Not a multiple of any schedule. The old warning text claimed '2x schedule
        interval', which pointed operators at a setting that does not control it."""
        recent = manifest(completed_at="2026-08-21T00:00:00Z")  # 4 hours old
        assert evaluate(recent, settings(backup_staleness_hours=2)).status is (
            BackupFreshnessStatus.STALE
        )
        assert evaluate(recent, settings(backup_staleness_hours=48)).status is (
            BackupFreshnessStatus.OK
        )

    def test_absent_manifest_is_no_history_not_an_error(self) -> None:
        assert evaluate(manifest_reader._ABSENT).status is BackupFreshnessStatus.NO_HISTORY

    def test_an_unreachable_target_is_unknown_and_distinguishable(self) -> None:
        """`no_history` means no backup has run. `unknown` means we could not find
        out. Reporting either as the other sends the operator to the wrong system."""
        assert evaluate(None).status is BackupFreshnessStatus.UNKNOWN
        assert evaluate(manifest_reader._ABSENT).status is not evaluate(None).status

    def test_disabled_monitoring_reports_no_status_and_no_alert(self) -> None:
        freshness = evaluate(manifest(), settings(backup_monitoring_enabled=False))
        assert freshness.status is BackupFreshnessStatus.NOT_CONFIGURED
        assert freshness.alertable is False

    def test_the_disable_decision_comes_from_the_neutral_setting(self) -> None:
        cfg = settings(backup_monitoring_enabled=False)
        cfg.railway_backup_enabled = True  # legacy says on; neutral setting wins
        assert evaluate(manifest(), cfg).status is BackupFreshnessStatus.NOT_CONFIGURED

    def test_a_reader_failure_is_a_status_not_a_raise(self) -> None:
        """A readiness probe that 500s because a bucket is slow has turned a
        monitoring signal into an outage."""

        def boom(_settings: Any) -> Any:
            raise TimeoutError("bucket is slow")

        manifest_reader.reset_cache()
        with patch.object(manifest_reader, "_s3_client", boom):
            assert read_freshness(settings(), use_cache=False).status is (
                BackupFreshnessStatus.UNKNOWN
            )


class TestPartialRunsAreNotHealthy:
    def test_a_fresh_but_partial_manifest_is_not_ok(self) -> None:
        """A6.2 — freshness from timestamp ALONE reported a partial run as ok, which
        is exactly what D11 rejected when it dismissed reading freshness from a HEAD
        on the newest artifact."""
        partial = manifest(overall_outcome="partial")
        assert evaluate(partial).status is BackupFreshnessStatus.PARTIAL

    def test_a_failed_store_makes_a_fresh_run_partial(self) -> None:
        with_failure = manifest(
            stores=[
                {"store": "postgres", "outcome": "succeeded", "required": True},
                {"store": "artifacts", "outcome": "failed", "required": False, "reason": "x"},
            ]
        )
        assert evaluate(with_failure).status is BackupFreshnessStatus.PARTIAL

    def test_partial_raises_its_own_diagnostic_code(self) -> None:
        assert evaluate(manifest(overall_outcome="partial")).diagnostic_code == "backup_partial"

    def test_staleness_outranks_partial(self) -> None:
        """An old partial run is stale first: age is the more urgent fact."""
        old_partial = manifest(completed_at="2026-08-01T03:00:00Z", overall_outcome="partial")
        assert evaluate(old_partial).status is BackupFreshnessStatus.STALE


class TestEnvironmentIsolation:
    def test_a_foreign_environment_is_rejected(self) -> None:
        freshness = evaluate(manifest(environment="staging"))
        assert freshness.status is BackupFreshnessStatus.ENVIRONMENT_MISMATCH
        assert freshness.diagnostic_code == "backup_environment_mismatch"

    def test_a_mismatch_is_never_reported_as_ok(self) -> None:
        """Otherwise production backups can stop entirely while /ready says ok."""
        assert evaluate(manifest(environment="staging")).status is not BackupFreshnessStatus.OK


class TestBoundedAndNonBlocking:
    def test_repeated_probes_do_not_each_issue_a_network_read(self) -> None:
        calls = {"n": 0}

        def counting(_settings: Any) -> Any:
            calls["n"] += 1
            return manifest()

        manifest_reader.reset_cache()
        clock = {"t": 0.0}
        with patch.object(manifest_reader, "_fetch_manifest", counting):
            for _ in range(5):
                clock["t"] += 1.0
                read_freshness(settings(), now=NOW, monotonic=lambda: clock["t"])
        assert calls["n"] == 1

    def test_the_cache_expires(self) -> None:
        calls = {"n": 0}

        def counting(_settings: Any) -> Any:
            calls["n"] += 1
            return manifest()

        manifest_reader.reset_cache()
        clock = {"t": 0.0}
        with patch.object(manifest_reader, "_fetch_manifest", counting):
            read_freshness(settings(), now=NOW, monotonic=lambda: clock["t"])
            clock["t"] = manifest_reader.CACHE_TTL_SECONDS + 1
            read_freshness(settings(), now=NOW, monotonic=lambda: clock["t"])
        assert calls["n"] == 2

    def test_the_client_declares_explicit_short_timeouts(self) -> None:
        captured: dict[str, Any] = {}

        class FakeBoto:
            @staticmethod
            def client(_service: str, **kwargs: Any) -> Any:
                captured.update(kwargs)
                return object()

        with patch.dict("sys.modules", {"boto3": FakeBoto}):
            manifest_reader._s3_client(settings())
        config = captured["config"]
        assert config.connect_timeout <= 5
        assert config.read_timeout <= 5


# ------------------------------------------------------------------ check window


class TestCheckWindowKeying:
    def test_every_evaluation_inside_one_window_derives_the_same_key(self) -> None:
        """A10 — the suffix is the window START, not a wall-clock read. This is the
        entire idempotency mechanism, so it is asserted directly."""
        cfg = settings(backup_staleness_hours=48)
        base = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
        keys = {
            event_key_for(cfg, base + timedelta(minutes=minutes)) for minutes in (0, 1, 59, 60, 600)
        }
        assert len(keys) == 1

    def test_a_later_window_derives_a_different_key(self) -> None:
        """Re-alerting is what distinguishes an ongoing outage from a blip."""
        cfg = settings(backup_staleness_hours=1)
        first = event_key_for(cfg, datetime(2026, 8, 21, 0, 30, tzinfo=UTC))
        second = event_key_for(cfg, datetime(2026, 8, 21, 1, 30, tzinfo=UTC))
        assert first != second

    def test_the_window_length_equals_the_staleness_threshold(self) -> None:
        assert window_seconds_for(settings(backup_staleness_hours=48)) == 48 * 3600

    def test_a_zero_threshold_cannot_make_every_tick_its_own_window(self) -> None:
        """Otherwise a misconfiguration turns the alert channel into a firehose,
        which is the fastest way to train operators to ignore it."""
        assert window_seconds_for(settings(backup_staleness_hours=0)) == MIN_WINDOW_SECONDS

    def test_the_key_matches_the_lowercase_grammar_the_model_enforces(self) -> None:
        """Both earlier candidate grammars embedded an ISO-8601 stamp, whose
        uppercase T/Z fail WorkflowEventKey — every alert would have been rejected
        at construction. Asserted against the model, not against a copy of it."""
        from pydantic import TypeAdapter

        from src.contracts.workflow_alert_models import WorkflowEventKey

        key = event_key_for(settings(), NOW)
        TypeAdapter(WorkflowEventKey).validate_python(key)

    def test_truncation_is_a_pure_function_of_the_window(self) -> None:
        window = 3600
        for offset in (0, 1, 1799, 3599):
            moment = datetime(2026, 8, 21, 5, 0, tzinfo=UTC) + timedelta(seconds=offset)
            assert check_window_start(moment, window_seconds=window) == int(
                datetime(2026, 8, 21, 5, 0, tzinfo=UTC).timestamp()
            )


# --------------------------------------------------------------------- emission


class FakeConn:
    def __init__(self, *, conflict: bool = False) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._conflict = conflict

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.calls.append((query, args))
        return None if self._conflict else "event-id"


@pytest.mark.asyncio
class TestWorkerEmission:
    async def test_a_stale_backup_enqueues_one_durable_event(self) -> None:
        conn = FakeConn()
        with patch(
            "src.services.backup_freshness_alert.read_freshness",
            lambda *_a, **_k: _stale(),
        ):
            key = await emit_backup_freshness_alert(conn, settings=settings(), now=NOW)
        assert key is not None
        assert len(conn.calls) == 1
        assert "workflow_terminal_events" in conn.calls[0][0]
        assert "'system_check'" in conn.calls[0][0]

    async def test_a_healthy_backup_emits_nothing(self) -> None:
        conn = FakeConn()
        with patch(
            "src.services.backup_freshness_alert.read_freshness",
            lambda *_a, **_k: _ok(),
        ):
            assert await emit_backup_freshness_alert(conn, settings=settings(), now=NOW) is None
        assert conn.calls == []

    async def test_disabled_monitoring_emits_nothing(self) -> None:
        conn = FakeConn()
        cfg = settings(backup_monitoring_enabled=False)
        assert await emit_backup_freshness_alert(conn, settings=cfg, now=NOW) is None
        assert conn.calls == []

    async def test_a_second_evaluation_in_the_same_window_does_not_duplicate(self) -> None:
        conn = FakeConn(conflict=True)
        with patch(
            "src.services.backup_freshness_alert.read_freshness",
            lambda *_a, **_k: _stale(),
        ):
            assert await emit_backup_freshness_alert(conn, settings=settings(), now=NOW) is None

    async def test_the_insert_relies_on_the_unique_event_key(self) -> None:
        conn = FakeConn()
        with patch(
            "src.services.backup_freshness_alert.read_freshness",
            lambda *_a, **_k: _stale(),
        ):
            await emit_backup_freshness_alert(conn, settings=settings(), now=NOW)
        assert "ON CONFLICT (event_key) DO NOTHING" in conn.calls[0][0]

    async def test_the_row_carries_no_operation_or_reconciliation_identity(self) -> None:
        conn = FakeConn()
        with patch(
            "src.services.backup_freshness_alert.read_freshness",
            lambda *_a, **_k: _stale(),
        ):
            await emit_backup_freshness_alert(conn, settings=settings(), now=NOW)
        query = conn.calls[0][0]
        for column in ("operation_id", "claim_generation", "reconciliation_run_id"):
            assert column not in query


class TestReadinessNeverEmits:
    def test_the_readiness_module_does_not_import_the_emitter(self) -> None:
        """Polling readiness must not multiply alerts. Asserted structurally, so a
        future edit that reaches for the emitter from /ready fails here."""
        import inspect

        from src.api import health_routes

        source = inspect.getsource(health_routes)
        assert "emit_backup_freshness_alert" not in source
        assert "backup_freshness_alert" not in source

    def test_readiness_reads_freshness_and_nothing_more(self) -> None:
        import inspect

        from src.api import health_routes

        source = inspect.getsource(health_routes._check_backup_recency)
        assert "read_freshness" in source
        assert "INSERT" not in source.upper()


def _stale() -> Any:
    from src.services.backup.manifest_reader import BackupFreshness

    return BackupFreshness(
        status=BackupFreshnessStatus.STALE,
        manifest_age_seconds=200_000,
        stores_succeeded=3,
    )


def _ok() -> Any:
    from src.services.backup.manifest_reader import BackupFreshness

    return BackupFreshness(status=BackupFreshnessStatus.OK, manifest_age_seconds=60)
