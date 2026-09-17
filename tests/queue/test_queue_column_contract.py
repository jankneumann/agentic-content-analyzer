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
