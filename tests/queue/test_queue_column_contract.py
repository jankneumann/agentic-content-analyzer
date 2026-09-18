"""Every column the code names on ``pgqueuer_jobs`` must actually exist.

The claim query asked for ``root_operation_id`` while the migration and the
schema verifier both call that column ``root_job_id``, and so did the SET list
that stamps a submission context. Every claim and every submission raised
``UndefinedColumnError``: the worker and the scheduler crash-looped until
Podman stopped restarting them, and two observability endpoints answered 500.
Nothing caught it, because the claim test hands ``_claim_jobs`` a ``MagicMock``
connection and no database ever parses that SQL.

These tests read the SQL instead. Every identifier a statement selects,
returns, or assigns on ``pgqueuer_jobs`` is checked against
``REQUIRED_QUEUE_COLUMNS`` -- the same set the runtime verifies the live schema
against, so the two can never drift apart silently.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.queue.setup import REQUIRED_QUEUE_COLUMNS

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"

_TABLE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
_SELECT = re.compile(r"\bSELECT\s+(.+?)\s+FROM\b", re.IGNORECASE | re.DOTALL)
_RETURNING = re.compile(r"\bRETURNING\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)
_SET = re.compile(r"\bSET\s+(.+?)\bWHERE\b", re.IGNORECASE | re.DOTALL)
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_STRING_LITERAL = re.compile(r'"""(.*?)"""|"([^"\n]*)"', re.DOTALL)
_LITERALS = {"true", "false", "null", "now", "default"}
_LOCKING = re.compile(r"\bFOR\s+(?:UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", re.IGNORECASE)


def _columns(fragment: str) -> set[str]:
    """Plain column names in a comma-separated SQL list; expressions skipped."""
    found: set[str] = set()
    for item in fragment.split(","):
        name = item.strip().split("=", 1)[0].strip()
        name = re.split(r"\s+AS\s+", name, flags=re.IGNORECASE)[0].strip().lower()
        if _IDENTIFIER.fullmatch(name) and name not in _LITERALS:
            found.add(name)
    return found


def _statements_on_the_queue_table(text: str) -> list[str]:
    """Statements whose only table is pgqueuer_jobs, so this set describes them."""
    statements = []
    for match in _STRING_LITERAL.finditer(text):
        sql = match.group(1) or match.group(2) or ""
        for statement in sql.split(";"):
            # `FOR UPDATE SKIP LOCKED` is a locking clause, not a table.
            tables = {name.lower() for name in _TABLE.findall(_LOCKING.sub(" ", statement))}
            if tables == {"pgqueuer_jobs"}:
                statements.append(statement)
    return statements


def _referenced_columns() -> dict[str, set[str]]:
    referenced: dict[str, set[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "pgqueuer_jobs" not in text:
            continue
        columns: set[str] = set()
        for statement in _statements_on_the_queue_table(text):
            for pattern in (_SELECT, _SET, _RETURNING):
                for hit in pattern.finditer(statement):
                    columns |= _columns(hit.group(1))
        if columns:
            referenced[str(path.relative_to(SOURCE_ROOT.parent))] = columns
    return referenced


def test_the_scanner_reaches_the_queue_sql_it_is_meant_to_guard() -> None:
    referenced = _referenced_columns()
    assert "src/queue/worker.py" in referenced
    assert "src/services/operation_service.py" in referenced
    assert "root_job_id" in referenced["src/queue/worker.py"]
    assert "root_job_id" in referenced["src/services/operation_service.py"]


def test_no_source_file_names_a_column_pgqueuer_jobs_does_not_have() -> None:
    unknown = {
        path: sorted(columns - REQUIRED_QUEUE_COLUMNS)
        for path, columns in _referenced_columns().items()
        if columns - REQUIRED_QUEUE_COLUMNS
    }
    assert not unknown, f"columns absent from the queue schema: {unknown}"


def test_the_submission_context_constraint_admits_exactly_the_envelope_fields() -> None:
    """``OperationContextEnvelope`` is a closed contract in two places at once:
    Pydantic requires every field to be present, and a CHECK constraint on
    ``pgqueuer_jobs.submission_context`` refuses any key outside its list. The
    GX-10 work added ``authority_fingerprint`` and ``ownership_epoch`` to the
    model and not to the constraint, so once submissions reached the column
    every one of them was refused by the database. Adding a field to the
    envelope means writing a migration; this test is what says so."""
    import importlib.util

    from src.contracts.workflow_models import OperationContextEnvelope

    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/f3a91c5d7e28_admit_gx10_authority_in_submission_context.py"
    )
    spec = importlib.util.spec_from_file_location("_submission_context_migration", migration)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    allowed = set(module._ENVELOPE_KEYS) | set(module._AUTHORITY_KEYS)
    assert allowed == set(OperationContextEnvelope.model_fields)


def test_the_submission_write_sets_every_column_the_identity_check_requires() -> None:
    """``ck_pgqueuer_jobs_context_identity`` refuses a stored context whose
    correlation columns do not mirror it, and it names six of them. The
    submission write set five: ``submission_span_id`` stayed NULL, so the
    database rejected every submission and the API answered 500 on ingest.
    The required list is read from the migration, so widening the constraint
    without widening the write fails here rather than in production."""
    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/e4b7c9d2a610_add_operation_observability.py"
    ).read_text(encoding="utf-8")
    identity = migration.split("ADD CONSTRAINT ck_pgqueuer_jobs_context_identity CHECK (", 1)[
        1
    ].split("\n            ),", 1)[0]
    required = set(re.findall(r"\b(?:root_job_id|trace_id|submission_[a-z_]+)\b", identity))
    assert "submission_span_id" in required  # the one that was missing

    service = (
        Path(__file__).resolve().parents[2] / "src/services/operation_service.py"
    ).read_text(encoding="utf-8")
    written: set[str] = set()
    for statement in _statements_on_the_queue_table(service):
        if "submission_context" not in statement or "UPDATE" not in statement.upper():
            continue
        for hit in _SET.finditer(statement):
            written |= _columns(hit.group(1))
    assert required <= written, f"never written: {sorted(required - written)}"
