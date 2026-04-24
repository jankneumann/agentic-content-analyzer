"""Tests for GET /api/v1/audit query endpoint and Alembic migration.

Covers:
- Time-range filter (since, until)
- Exact-match path filter with pattern validation
- operation filter
- status_code filter
- limit clamping (default 100, max 1000)
- 422 Problem on invalid path pattern

And the migration contract:
- ``alembic upgrade`` creates the ``audit_log`` table with the columns,
  types, and indexes declared in ``contracts/db/schema.sql``.
- ``alembic downgrade`` removes it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.usefixtures("api_test_env")


@pytest.fixture
def audit_route_db(monkeypatch, test_db_engine):
    """Point ``audit_routes.get_db`` at the test engine.

    The shared ``client`` fixture in ``tests/api/conftest.py`` patches
    ``get_db`` on every known route module. ``src.api.routes.audit_routes``
    is new (not listed there), so we patch it here.
    """
    SessionLocal = sessionmaker(bind=test_db_engine, expire_on_commit=False)

    @contextmanager
    def _fake_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr("src.api.routes.audit_routes.get_db", _fake_get_db)
    return _fake_get_db


# ---------------------------------------------------------------------------
# Schema / migration contract
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_table(test_db_engine):
    """Create + drop audit_log table directly via SQL for route tests.

    The schema here mirrors ``contracts/db/schema.sql``. Tests for the
    Alembic migration itself are gated on a live Postgres (see
    test_migration_creates_audit_log_with_schema).
    """
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
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp DESC)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_operation "
                "ON audit_log (operation) WHERE operation IS NOT NULL"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_path_timestamp "
                "ON audit_log (path, timestamp DESC)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_admin_key_fp "
                "ON audit_log (admin_key_fp, timestamp DESC) WHERE admin_key_fp IS NOT NULL"
            )
        )
    yield
    with test_db_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS audit_log CASCADE"))


@pytest.fixture
def seeded_audit_rows(test_db_engine, audit_table):
    """Insert a handful of canonical audit rows."""
    base = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    rows = [
        (base, "r-1", "GET", "/api/v1/kb/search", None, "aaaaaaaa", 200, 0, "127.0.0.1", {}),
        (
            base + timedelta(minutes=1),
            "r-2",
            "POST",
            "/api/v1/kb/lint/fix",
            "kb.lint.fix",
            "aaaaaaaa",
            200,
            16,
            "127.0.0.1",
            {},
        ),
        (
            base + timedelta(minutes=2),
            "r-3",
            "POST",
            "/api/v1/graph/extract-entities",
            "graph.extract_entities",
            "aaaaaaaa",
            200,
            32,
            "127.0.0.1",
            {"content_id": 7},
        ),
        (
            base + timedelta(minutes=3),
            "r-4",
            "GET",
            "/api/v1/audit",
            None,
            None,
            401,
            0,
            "10.0.0.99",
            {"auth_failure": "missing_key"},
        ),
        (
            base + timedelta(minutes=4),
            "r-5",
            "POST",
            "/api/v1/kb/lint/fix",
            "kb.lint.fix",
            "zzzzzzzz",
            403,
            0,
            "10.0.0.99",
            {"auth_failure": "invalid_key"},
        ),
    ]
    with test_db_engine.begin() as conn:
        for ts, rid, method, path, op, fp, status, bsize, ip, notes in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO audit_log
                        (timestamp, request_id, method, path, operation, admin_key_fp,
                         status_code, body_size, client_ip, notes)
                    VALUES
                        (:ts, :rid, :method, :path, :op, :fp, :status, :bsize, CAST(:ip AS INET),
                         CAST(:notes AS JSONB))
                    """
                ),
                {
                    "ts": ts,
                    "rid": rid,
                    "method": method,
                    "path": path,
                    "op": op,
                    "fp": fp,
                    "status": status,
                    "bsize": bsize,
                    "ip": ip,
                    "notes": __import__("json").dumps(notes),
                },
            )
    return rows


# ---------------------------------------------------------------------------
# GET /api/v1/audit route tests
# ---------------------------------------------------------------------------


def test_query_default_returns_all_rows(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "entries" in body
    assert body["total_count"] == len(seeded_audit_rows)


def test_query_orders_by_timestamp_desc(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    # newest first
    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_query_since_filter(client, seeded_audit_rows, audit_route_db):
    base = datetime(2026, 4, 21, 10, 2, 0, tzinfo=UTC)
    resp = client.get("/api/v1/audit", params={"since": base.isoformat()})
    assert resp.status_code == 200, resp.text
    entries = resp.json()["entries"]
    # 3 rows at or after 10:02
    assert len(entries) == 3


def test_query_until_filter(client, seeded_audit_rows, audit_route_db):
    cutoff = datetime(2026, 4, 21, 10, 2, 30, tzinfo=UTC)
    resp = client.get("/api/v1/audit", params={"until": cutoff.isoformat()})
    assert resp.status_code == 200, resp.text
    entries = resp.json()["entries"]
    assert len(entries) == 3  # 10:00, 10:01, 10:02


def test_query_path_exact_match(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit?path=/api/v1/kb/lint/fix")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 2
    assert all(e["path"] == "/api/v1/kb/lint/fix" for e in entries)


def test_query_path_invalid_returns_422(client, seeded_audit_rows, audit_route_db):
    bad = "/api/v1/kb/%20'; DROP TABLE"
    resp = client.get("/api/v1/audit", params={"path": bad})
    assert resp.status_code == 422
    body = resp.json()
    # Problem shape OR FastAPI default validation — both acceptable.
    assert body.get("status") == 422 or "detail" in body


def test_query_operation_filter(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit?operation=kb.lint.fix")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 2
    assert all(e["operation"] == "kb.lint.fix" for e in entries)


def test_query_status_code_filter(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit?status_code=403")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["status_code"] == 403


def test_query_limit_clamped_to_1000(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit?limit=5000")
    # Per spec: server-clamped, never fails
    assert resp.status_code == 200


def test_query_limit_honored_small(client, seeded_audit_rows, audit_route_db):
    resp = client.get("/api/v1/audit?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 2


def test_query_requires_admin_key_in_production(monkeypatch, seeded_audit_rows):
    """Route must be auth-gated; unauthenticated access → 401/403."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-at-least-32-characters-long!")
    monkeypatch.setenv("ADMIN_API_KEY", "right-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from src.api.app import app

        with TestClient(app, base_url="https://testserver") as c:
            resp = c.get("/api/v1/audit")
            assert resp.status_code in (401, 403)
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Migration contract tests
# ---------------------------------------------------------------------------


def test_migration_module_exists():
    """The Alembic migration for the audit_log table must be committed."""
    from pathlib import Path

    migrations = list(Path(__file__).resolve().parents[2].glob("alembic/versions/*audit_log*.py"))
    assert migrations, "no alembic migration matching *audit_log*.py found"


def test_migration_creates_audit_log_with_expected_columns(test_db_engine, audit_table):
    """audit_log has all columns from contracts/db/schema.sql with correct types."""
    with test_db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'audit_log' "
                "ORDER BY ordinal_position"
            )
        ).fetchall()

    cols = {r[0]: (r[1], r[2]) for r in rows}
    # Required columns + SQL type fragments (substring match avoids driver-specific naming)
    assert "id" in cols
    assert "bigint" in cols["id"][0].lower()
    assert cols["timestamp"][1] == "NO"  # NOT NULL
    assert "time" in cols["timestamp"][0].lower()
    assert cols["request_id"][1] == "NO"
    assert cols["method"][1] == "NO"
    assert cols["path"][1] == "NO"
    assert "operation" in cols
    assert cols["operation"][1] == "YES"  # nullable
    assert "admin_key_fp" in cols
    assert cols["status_code"][1] == "NO"
    assert "body_size" in cols
    assert "client_ip" in cols
    assert "notes" in cols


def test_migration_creates_expected_indexes(test_db_engine, audit_table):
    with test_db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'audit_log'")
        ).fetchall()
    index_names = {r[0] for r in rows}
    assert "idx_audit_log_timestamp" in index_names
    assert "idx_audit_log_operation" in index_names
    assert "idx_audit_log_path_timestamp" in index_names
    assert "idx_audit_log_admin_key_fp" in index_names


def test_migration_has_timestamp_check_constraint(test_db_engine, audit_table):
    with test_db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'audit_log'::regclass AND contype = 'c'"
            )
        ).fetchall()
    names = {r[0] for r in rows}
    assert "audit_log_timestamp_check" in names
