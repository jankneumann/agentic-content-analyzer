"""PostgreSQL evidence for the operation-observability persistence contract."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from src.queue import setup as queue_setup
from src.repositories.operation_observation_attempts import (
    AttemptCompletion,
    AttemptStart,
    complete_attempt,
    list_attempts,
    record_stale_claim_diagnostic,
    start_attempt,
)
from src.repositories.telemetry_process_health import (
    ProcessHealthHeartbeat,
    cleanup_expired_process_health,
    list_process_health,
    upsert_process_health,
)

TRACE_ID = "1" * 32
SPAN_ID = "2" * 16
TRACEPARENT = f"00-{TRACE_ID}-{SPAN_ID}-01"
BASE_ID = 9_710_000


async def _connect(test_engine) -> asyncpg.Connection:
    return await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))


def _context(operation_id: int, root_id: int, *, generation: int = 0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation_id": str(operation_id),
        "root_operation_id": str(root_id),
        "parent_operation_id": None,
        "traceparent": TRACEPARENT,
        "tracestate": None,
        "trace_id": TRACE_ID,
        "span_id": SPAN_ID,
        "claim_generation": str(generation),
        "attempt_number": None if generation == 0 else str(generation + 1),
        "entrypoint": "ingestion.execute",
        "service_name": "aca-api",
        "service_instance_id": "api-1",
        "environment": "test",
        "release_revision": "abc123",
        "stage": "submit",
        "resource_kind": None,
        "resource_key": None,
    }


async def _insert_job(
    conn: asyncpg.Connection, operation_id: int, *, status: str = "queued"
) -> None:
    await conn.execute(
        "INSERT INTO pgqueuer_jobs (id, entrypoint, payload, status) "
        "VALUES ($1, 'ingestion.execute', '{}'::jsonb, $2)",
        operation_id,
        status,
    )


async def _attach_context(
    conn: asyncpg.Connection, operation_id: int, context: dict[str, object], **overrides: object
) -> None:
    fields = {
        "root_job_id": int(context["root_operation_id"]),
        "submission_context": json.dumps(context),
        "submission_traceparent": context["traceparent"],
        "submission_tracestate": context["tracestate"],
        "trace_id": context["trace_id"],
        "submission_span_id": context["span_id"],
    }
    fields.update(overrides)
    await conn.execute(
        """UPDATE pgqueuer_jobs
        SET root_job_id=$2, submission_context=$3::jsonb, submission_traceparent=$4,
            submission_tracestate=$5, trace_id=$6, submission_span_id=$7 WHERE id=$1""",
        operation_id,
        fields["root_job_id"],
        fields["submission_context"],
        fields["submission_traceparent"],
        fields["submission_tracestate"],
        fields["trace_id"],
        fields["submission_span_id"],
    )


@pytest_asyncio.fixture
async def pg_conn(test_engine):
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_nullable_legacy_row_and_root_self_reference(pg_conn) -> None:
    await _insert_job(pg_conn, BASE_ID)
    legacy = await pg_conn.fetchrow(
        "SELECT root_job_id, submission_context, trace_id FROM pgqueuer_jobs WHERE id=$1", BASE_ID
    )
    assert tuple(legacy.values()) == (None, None, None)
    await _attach_context(pg_conn, BASE_ID, _context(BASE_ID, BASE_ID))
    assert await pg_conn.fetchval("SELECT root_job_id = id FROM pgqueuer_jobs WHERE id=$1", BASE_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("root_job_id", None),
        ("root_job_id", BASE_ID + 1),
        ("submission_traceparent", None),
        ("submission_traceparent", f"00-{'3' * 32}-{SPAN_ID}-01"),
        ("submission_tracestate", "vendor=other"),
        ("trace_id", None),
        ("trace_id", "3" * 32),
        ("submission_span_id", None),
        ("submission_span_id", "3" * 16),
    ],
)
async def test_every_null_or_mismatched_duplicate_context_field_is_rejected(
    pg_conn, field: str, value: object
) -> None:
    await _insert_job(pg_conn, BASE_ID)
    if field == "root_job_id" and value == BASE_ID + 1:
        await _insert_job(pg_conn, BASE_ID + 1)
    with pytest.raises(asyncpg.CheckViolationError):
        await _attach_context(pg_conn, BASE_ID, _context(BASE_ID, BASE_ID), **{field: value})


@pytest.mark.asyncio
async def test_context_rejects_unknown_keys_and_json_null_required_identity(pg_conn) -> None:
    await _insert_job(pg_conn, BASE_ID)
    unknown = _context(BASE_ID, BASE_ID)
    unknown["secret"] = "must-not-persist"
    with pytest.raises(asyncpg.CheckViolationError):
        async with pg_conn.transaction():
            await _attach_context(pg_conn, BASE_ID, unknown)
    for field in ("operation_id", "root_operation_id", "traceparent", "trace_id", "span_id"):
        invalid = _context(BASE_ID, BASE_ID)
        invalid[field] = None
        with pytest.raises((asyncpg.CheckViolationError, asyncpg.DataError, TypeError, ValueError)):
            async with pg_conn.transaction():
                await _attach_context(pg_conn, BASE_ID, invalid)


@pytest.mark.asyncio
async def test_signed_bigint_boundaries_and_generation_plus_one_overflow(pg_conn) -> None:
    max_id = 9_223_372_036_854_775_807
    await _insert_job(pg_conn, max_id)
    await _attach_context(pg_conn, max_id, _context(max_id, max_id))
    assert await pg_conn.fetchval("SELECT id FROM pgqueuer_jobs WHERE id=$1", max_id) == max_id
    with pytest.raises(asyncpg.NumericValueOutOfRangeError):
        async with pg_conn.transaction():
            await pg_conn.execute(
                "INSERT INTO pgqueuer_jobs (id, entrypoint) VALUES ($1::numeric, 'x')", max_id + 1
            )
    await pg_conn.execute(
        "UPDATE pgqueuer_jobs SET claim_generation=$2 WHERE id=$1", max_id, max_id - 1
    )
    await pg_conn.execute(
        """INSERT INTO operation_observation_attempts (
        operation_id,claim_generation,attempt_number,trace_id,service_name,
        service_instance_id,environment,release_revision,started_at)
        VALUES ($1,$2,$3,$4,'worker','one','test','rev',NOW())""",
        max_id,
        max_id - 1,
        max_id,
        TRACE_ID,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await pg_conn.execute(
            """INSERT INTO operation_observation_attempts (
            operation_id,claim_generation,attempt_number,trace_id,service_name,
            service_instance_id,environment,release_revision,started_at)
            VALUES ($1,$2,$3,$4,'worker','one','test','rev',NOW())""",
            max_id,
            max_id,
            max_id,
            TRACE_ID,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "codes",
    [
        ["UPPERCASE"],
        ["x" * 101],
        ["ok"] * 21,
    ],
)
async def test_diagnostic_type_cardinality_and_byte_constraints(pg_conn, codes: list[str]) -> None:
    await _insert_job(pg_conn, BASE_ID, status="in_progress")
    with pytest.raises((asyncpg.CheckViolationError, asyncpg.StringDataRightTruncationError)):
        await pg_conn.execute(
            """INSERT INTO operation_observation_attempts (
            operation_id,claim_generation,attempt_number,trace_id,service_name,
            service_instance_id,environment,release_revision,started_at,diagnostic_codes)
            VALUES ($1,0,1,$2,'worker','one','test','rev',NOW(),$3)""",
            BASE_ID,
            TRACE_ID,
            codes,
        )


@pytest.mark.asyncio
async def test_attempt_repository_ordering_and_fencing(pg_conn) -> None:
    await _insert_job(pg_conn, BASE_ID)
    await pg_conn.execute(
        "UPDATE pgqueuer_jobs SET status='in_progress', claim_generation=1 WHERE id=$1", BASE_ID
    )

    def attempt(generation: int) -> AttemptStart:
        return AttemptStart(
            operation_id=BASE_ID,
            claim_generation=generation,
            trace_id=TRACE_ID,
            root_span_id=SPAN_ID,
            langfuse_observation_id=f"obs-{generation}",
            service_name="worker",
            service_instance_id="one",
            environment="test",
            release_revision="rev",
            started_at=datetime.now(UTC),
        )

    assert await start_attempt(pg_conn, attempt(1))
    assert not await start_attempt(pg_conn, attempt(0))
    await pg_conn.execute("UPDATE pgqueuer_jobs SET claim_generation=2 WHERE id=$1", BASE_ID)
    assert await start_attempt(pg_conn, attempt(2))
    completion = AttemptCompletion(
        completed_at=datetime.now(UTC),
        terminal_stage="persist",
        outcome="succeeded",
        retryable=False,
        telemetry_delivery_state="delivered",
        diagnostic_codes=(),
        diagnostics_omitted=0,
    )
    assert not await complete_attempt(pg_conn, BASE_ID, 1, completion)
    assert await complete_attempt(pg_conn, BASE_ID, 2, completion)
    attempts = await list_attempts(pg_conn, BASE_ID)
    assert [item.claim_generation for item in attempts] == [1, 2]
    assert all(item.trace_id == TRACE_ID for item in attempts)


@pytest.mark.asyncio
async def test_stale_claim_only_marks_its_own_bounded_evidence(pg_conn) -> None:
    await _insert_job(pg_conn, BASE_ID, status="in_progress")
    attempt = AttemptStart(
        operation_id=BASE_ID,
        claim_generation=0,
        trace_id=TRACE_ID,
        root_span_id=SPAN_ID,
        langfuse_observation_id="stale",
        service_name="worker",
        service_instance_id="one",
        environment="test",
        release_revision="rev",
        started_at=datetime.now(UTC),
    )
    assert await start_attempt(pg_conn, attempt)
    await pg_conn.execute(
        "UPDATE pgqueuer_jobs SET claim_generation=1 WHERE id=$1", BASE_ID
    )
    current = AttemptStart(
        operation_id=BASE_ID,
        claim_generation=1,
        trace_id="3" * 32,
        root_span_id="4" * 16,
        langfuse_observation_id="current",
        service_name="worker",
        service_instance_id="two",
        environment="test",
        release_revision="rev",
        started_at=datetime.now(UTC),
    )
    assert await start_attempt(pg_conn, current)

    assert await record_stale_claim_diagnostic(pg_conn, BASE_ID, 0)
    assert await record_stale_claim_diagnostic(pg_conn, BASE_ID, 0)
    job = await pg_conn.fetchrow(
        "SELECT status, claim_generation FROM pgqueuer_jobs WHERE id=$1", BASE_ID
    )
    rows = await pg_conn.fetch(
        """SELECT claim_generation, completed_at, diagnostic_codes, diagnostics_omitted
        FROM operation_observation_attempts WHERE operation_id=$1
        ORDER BY claim_generation""",
        BASE_ID,
    )
    assert dict(job) == {"status": "in_progress", "claim_generation": 1}
    assert list(rows[0]["diagnostic_codes"]) == ["queue.stale_claim"]
    assert rows[0]["completed_at"] is None
    assert list(rows[1]["diagnostic_codes"]) == []
    assert rows[1]["diagnostics_omitted"] == 0

    full_codes = [f"test.code_{index:02d}" for index in range(20)]
    await pg_conn.execute(
        """UPDATE operation_observation_attempts
        SET diagnostic_codes=$3::operation_diagnostic_code[], diagnostics_omitted=3
        WHERE operation_id=$1 AND claim_generation=$2""",
        BASE_ID,
        0,
        full_codes,
    )
    assert await record_stale_claim_diagnostic(pg_conn, BASE_ID, 0)
    bounded = await pg_conn.fetchrow(
        """SELECT diagnostic_codes, diagnostics_omitted
        FROM operation_observation_attempts
        WHERE operation_id=$1 AND claim_generation=$2""",
        BASE_ID,
        0,
    )
    assert list(bounded["diagnostic_codes"]) == full_codes
    assert bounded["diagnostics_omitted"] == 4


@pytest.mark.asyncio
async def test_retention_deletes_attempts_before_root_and_preserves_failed_graph(pg_conn) -> None:
    success_id, failed_id = BASE_ID, BASE_ID + 10
    for operation_id, status, age in (
        (success_id, "completed", timedelta(days=31)),
        (failed_id, "failed", timedelta(days=31)),
    ):
        await _insert_job(pg_conn, operation_id, status=status)
        await pg_conn.execute(
            "UPDATE pgqueuer_jobs SET completed_at=NOW()-$2::interval WHERE id=$1",
            operation_id,
            age,
        )
        await pg_conn.execute(
            """INSERT INTO operation_observation_attempts (
            operation_id,claim_generation,attempt_number,trace_id,service_name,
            service_instance_id,environment,release_revision,started_at,completed_at,outcome)
            VALUES ($1,0,1,$2,'worker','one','test','rev',NOW()-$3::interval,
                    NOW()-$3::interval,$4)""",
            operation_id,
            TRACE_ID,
            age,
            "succeeded" if status == "completed" else "permanent_failure",
        )
    deleted = await queue_setup.cleanup_old_jobs(
        older_than_days=30, failed_older_than_days=90, conn=pg_conn
    )
    assert deleted == 1
    assert not await pg_conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM operation_observation_attempts WHERE operation_id=$1)",
        success_id,
    )
    assert await pg_conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM operation_observation_attempts WHERE operation_id=$1)",
        failed_id,
    )


@pytest.mark.asyncio
async def test_process_health_exact_expiry_freshness_restart_churn_and_cleanup(pg_conn) -> None:
    now = datetime(2026, 8, 29, tzinfo=UTC)
    for index in range(1002):
        heartbeat_at = now - timedelta(seconds=index)
        lifecycle = "long_running" if index % 2 == 0 else "short_lived"
        await upsert_process_health(
            pg_conn,
            ProcessHealthHeartbeat(
                environment="test",
                service_name="worker",
                service_instance_id=f"instance-{index:04d}",
                release_revision="rev",
                lifecycle_kind=lifecycle,
                required_observability=True,
                initialized=True,
                status="healthy",
                export_target="local_langfuse",
                last_heartbeat_at=heartbeat_at,
                last_success_at=heartbeat_at,
                last_error_at=None,
                last_error_code=None,
                buffered_count=0,
                buffer_capacity=100,
                dropped_count=0,
                last_flush_at=None,
                last_flush_succeeded=None,
            ),
        )
    rows, omitted = await list_process_health(pg_conn, "test", now=now, limit=1000)
    assert len(rows) == 1000 and omitted == 2
    assert rows[0].service_instance_id == "instance-0000"
    assert rows[0].expires_at == rows[0].last_heartbeat_at + timedelta(hours=24)
    assert rows[1].expires_at == rows[1].last_heartbeat_at + timedelta(days=7)
    await pg_conn.execute(
        "UPDATE telemetry_process_health SET last_heartbeat_at=$1::timestamptz-INTERVAL '24 hours', expires_at=$1 "
        "WHERE service_instance_id='instance-1000'",
        now,
    )
    assert await cleanup_expired_process_health(pg_conn, now=now) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("audit_log", "trace_id", "0" * 32),
        ("audit_log", "request_span_id", "0" * 16),
        ("workflow_terminal_events", "trace_id", "0" * 32),
    ],
)
async def test_zero_correlation_identifiers_are_rejected_everywhere(
    pg_conn, table: str, column: str, value: str
) -> None:
    if table == "audit_log":
        row_id = await pg_conn.fetchval(
            "INSERT INTO audit_log (request_id,method,path,status_code) "
            "VALUES ('request-1','GET','/test',200) RETURNING id"
        )
    else:
        row_id = await pg_conn.fetchval(
            """INSERT INTO workflow_terminal_events (event_key,source_kind,occurred_at)
            VALUES ('system_check:backup_freshness:9710000','system_check',NOW()) RETURNING id"""
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pg_conn.execute(f"UPDATE {table} SET {column}=$2 WHERE id=$1", row_id, value)  # noqa: S608


def _load_migration():
    paths = list(Path("alembic/versions").glob("*_add_operation_observability.py"))
    assert len(paths) == 1
    spec = importlib.util.spec_from_file_location("operation_observability_migration", paths[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_ddl_parses_and_round_trips_upgrade_downgrade(test_engine) -> None:
    migration = _load_migration()
    with test_engine.connect() as connection:
        transaction = connection.begin()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert "operation_observation_attempts" not in tables
        assert "telemetry_process_health" not in tables
        assert "environment_ownership" not in tables
        migration.upgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert {
            "operation_observation_attempts",
            "telemetry_process_health",
            "environment_ownership",
        } <= tables
        transaction.rollback()
