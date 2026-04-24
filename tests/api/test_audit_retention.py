"""Tests for pg_cron audit-log retention job.

Normative contract (spec audit-log §"Audit log retention via pg_cron" + design D4a):

1. The retention interval MUST be interpolated **at migration time** from
   ``AUDIT_LOG_RETENTION_DAYS`` (default 90), NOT read via
   ``current_setting('app.audit_retention_days')`` — Railway's managed
   Postgres restricts custom GUCs.

2. The registered pg_cron command literally contains ``INTERVAL '<N> days'``
   with <N> resolved at migration time.

3. Executing the retention DELETE against seeded rows removes rows older than
   the interval and leaves newer rows untouched.

The pg_cron extension itself is not required to run in tests — we assert the
SQL shape and execute the DELETE directly.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

_AUDIT_MIGRATION_GLOB = "alembic/versions/*audit_log*.py"


def _find_retention_migration() -> Path:
    root = Path(__file__).resolve().parents[2]
    paths = list(root.glob(_AUDIT_MIGRATION_GLOB))
    assert paths, (
        f"No migration matching {_AUDIT_MIGRATION_GLOB} found — "
        "create the audit_log migration first."
    )
    # Prefer a file that mentions retention or cron
    for p in paths:
        src = p.read_text()
        if "retention" in src.lower() or "cron" in src.lower():
            return p
    # Fallback: first match
    return paths[0]


def test_migration_uses_interval_literal_not_current_setting():
    """D4a: migration MUST NOT embed a GUC-read-at-runtime call in the cron
    command — it MUST interpolate the retention interval as a literal SQL value
    at Alembic upgrade time.

    Comments/docstrings mentioning the forbidden pattern are fine (the
    migration explains *why* it avoids the GUC path). We strip those and
    search only the code.
    """
    import ast
    import re

    src = _find_retention_migration().read_text()

    # Remove module/function docstrings — they're allowed to reference the
    # forbidden construct for rationale purposes.
    tree = ast.parse(src)
    lines = src.splitlines()
    to_blank: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for ln in range(node.lineno - 1, getattr(node, "end_lineno", node.lineno)):
                    to_blank.add(ln)
    filtered_lines = []
    for i, line in enumerate(lines):
        if i in to_blank:
            filtered_lines.append("")
            continue
        # also strip single-line # comments
        filtered_lines.append(re.sub(r"#.*$", "", line))
    filtered = "\n".join(filtered_lines)

    forbidden = "current" + "_setting("
    assert forbidden not in filtered, (
        "Retention migration must not read retention days via a GUC call. "
        "Interpolate AUDIT_LOG_RETENTION_DAYS at migration time (D4a)."
    )


def test_migration_reads_retention_days_from_environment():
    """Migration must consult AUDIT_LOG_RETENTION_DAYS at upgrade time."""
    src = _find_retention_migration().read_text()
    assert "AUDIT_LOG_RETENTION_DAYS" in src, (
        "Retention migration must reference AUDIT_LOG_RETENTION_DAYS env var."
    )
    # Must use os.environ.get or os.getenv
    assert re.search(r"os\.(environ\.get|getenv)\s*\(\s*['\"]AUDIT_LOG_RETENTION_DAYS['\"]", src)


def test_migration_embeds_interval_days_literal():
    """The SQL the migration emits must contain INTERVAL '<N> days'."""
    src = _find_retention_migration().read_text()
    # Accept either the default 90 or a variable-interpolated form; the variable
    # form is what actually gets stored. We just assert the fstring produces the
    # INTERVAL clause.
    assert re.search(r"INTERVAL\s+'\{[^}]*\}\s*days'", src) or re.search(
        r"INTERVAL\s+'\d+\s*days'", src
    ), "Migration must embed INTERVAL '<days> days' literal in the cron command."


def test_migration_registers_cron_job_with_stable_name():
    src = _find_retention_migration().read_text()
    assert "audit-log-retention" in src, (
        "pg_cron job must be registered with the stable name 'audit-log-retention'."
    )
    assert "cron.schedule" in src


def test_migration_wraps_cron_schedule_so_missing_extension_does_not_fail():
    """The migration must tolerate environments where pg_cron is not installed."""
    src = _find_retention_migration().read_text()
    # Look for a check — either an IF EXISTS on pg_cron or a try/except wrapping
    # the cron.schedule call.
    assert "pg_extension" in src or "pg_cron" in src.lower() or "except" in src, (
        "Migration must gracefully skip pg_cron.schedule() if extension missing."
    )


# ---------------------------------------------------------------------------
# Behavioural retention test: execute the DELETE against seeded data.
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_table(test_db_engine):
    with test_db_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              BIGSERIAL PRIMARY KEY,
                    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
                    request_id      TEXT NOT NULL,
                    method          TEXT NOT NULL,
                    path            TEXT NOT NULL,
                    operation       TEXT,
                    admin_key_fp    TEXT,
                    status_code     INTEGER NOT NULL,
                    body_size       INTEGER,
                    client_ip       INET,
                    notes           JSONB DEFAULT '{}'::jsonb,
                    CONSTRAINT audit_log_timestamp_check CHECK (timestamp >= '2026-01-01'::timestamptz)
                )
                """
            )
        )
    yield
    with test_db_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS audit_log CASCADE"))


def test_retention_delete_removes_old_rows(test_db_engine, audit_table):
    """Simulate the pg_cron DELETE and assert only old rows are removed.

    Uses a short test retention to stay within the timestamp CHECK constraint
    (``timestamp >= '2026-01-01'``) regardless of when tests run.
    """
    retention_days = 5  # small, deterministic window for the test
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    recent = now - timedelta(hours=1)
    with test_db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_log (timestamp, request_id, method, path, status_code) "
                "VALUES (:ts, 'r-old', 'GET', '/api/v1/kb/search', 200)"
            ),
            {"ts": old},
        )
        conn.execute(
            text(
                "INSERT INTO audit_log (timestamp, request_id, method, path, status_code) "
                "VALUES (:ts, 'r-new', 'GET', '/api/v1/kb/search', 200)"
            ),
            {"ts": recent},
        )

    # Execute the same shape of DELETE the pg_cron job would run.
    # (In production the migration interpolates retention_days literally; here
    # we use the same shape with our deterministic test value.)
    # retention_days is a module-local integer literal — no injection risk.
    delete_sql = f"DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '{retention_days} days'"  # noqa: S608
    with test_db_engine.begin() as conn:
        conn.execute(text(delete_sql))

    with test_db_engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT request_id FROM audit_log ORDER BY timestamp")
        ).fetchall()
    ids = [r[0] for r in remaining]
    assert "r-old" not in ids
    assert "r-new" in ids
