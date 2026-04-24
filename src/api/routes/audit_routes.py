"""Audit log query endpoint.

Implements ``GET /api/v1/audit`` per
``openspec/changes/cloud-db-source-of-truth/specs/audit-log/spec.md``
§"Audit log query endpoint".

Supported filters:
- ``since`` / ``until`` — timestamp range (ISO 8601).
- ``path`` — EXACT match; pattern-validated to ``^[/a-zA-Z0-9_-]+$`` so
  wildcard injection is rejected at the validation layer.
- ``operation`` — exact match on the ``audit_log.operation`` column.
- ``status_code`` — exact integer match.
- ``limit`` — default 100, clamped to [1, 1000].

Requires ``X-Admin-Key`` (inherited via ``verify_admin_key`` dependency).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.api.dependencies import verify_admin_key
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["audit"],
    dependencies=[Depends(verify_admin_key)],
)


# ---------------------------------------------------------------------------
# Response schemas (aligned with contracts/generated/models.py)
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    request_id: str
    method: str = Field(..., examples=["POST"])
    path: str = Field(..., examples=["/api/v1/kb/purge"])
    operation: str | None = Field(None, examples=["kb.purge"])
    admin_key_fp: str | None = Field(
        None,
        description="Last 8 chars of SHA-256 hash of the admin key",
        examples=["a1b2c3d4"],
    )
    status_code: int
    body_size: int | None = None
    client_ip: str | None = None
    notes: dict[str, Any] | None = None


class AuditQueryResponse(BaseModel):
    entries: list[AuditLogEntry]
    total_count: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


_PATH_PATTERN = r"^[/a-zA-Z0-9_-]+$"
_OPERATION_PATTERN = r"^[a-z][a-z0-9._-]*$"


@router.get("", response_model=AuditQueryResponse)
@router.get("/", response_model=AuditQueryResponse)
async def query_audit_log(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    path: str | None = Query(
        default=None,
        pattern=_PATH_PATTERN,
        max_length=200,
        description="Exact match on the `path` column.",
    ),
    operation: str | None = Query(
        default=None,
        pattern=_OPERATION_PATTERN,
        max_length=100,
    ),
    status_code: int | None = Query(default=None, ge=100, le=599),
    limit: int = Query(default=100),
) -> AuditQueryResponse:
    """Return recent audit entries matching the given filters.

    Rows are ordered by ``timestamp DESC``. Per spec audit-log §"Query respects
    max limit", ``limit`` is server-clamped to [1, 1000] and MUST NOT fail
    validation — values ≤0 are clamped to 1, values >1000 are clamped to 1000.
    """
    # gemini IR-002 fix: no ``ge=1`` on the Query — we clamp in-handler instead
    # so `?limit=0` is a silent clamp-to-1 rather than a 422 rejection.
    clamped_limit = min(max(limit, 1), 1000)
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": clamped_limit}

    if since is not None:
        clauses.append("timestamp >= :since")
        params["since"] = since
    if until is not None:
        clauses.append("timestamp <= :until")
        params["until"] = until
    if path is not None:
        clauses.append("path = :path")
        params["path"] = path
    if operation is not None:
        clauses.append("operation = :operation")
        params["operation"] = operation
    if status_code is not None:
        clauses.append("status_code = :status_code")
        params["status_code"] = status_code

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    # ``where_sql`` is assembled from a closed vocabulary of hard-coded column
    # predicates; only the VALUES use :name placeholders.
    sql_str = f"SELECT id, timestamp, request_id, method, path, operation, admin_key_fp, status_code, body_size, HOST(client_ip) AS client_ip, notes FROM audit_log {where_sql} ORDER BY timestamp DESC LIMIT :limit"  # noqa: S608
    # IR-003 (gemini + claude): total_count reflects the FULL filtered match
    # count so pagination clients can compute "has more" correctly. Strip the
    # :limit bind param from the COUNT version so it doesn't reject the unused
    # placeholder.
    count_sql_str = f"SELECT COUNT(*) FROM audit_log {where_sql}"  # noqa: S608
    count_params = {k: v for k, v in params.items() if k != "limit"}
    sql = text(sql_str)
    count_sql = text(count_sql_str)

    with get_db() as db:
        result = db.execute(sql, params).fetchall()
        total_count = int(db.execute(count_sql, count_params).scalar() or 0)

    entries: list[AuditLogEntry] = []
    for row in result:
        mapping = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        entries.append(AuditLogEntry(**mapping))

    return AuditQueryResponse(entries=entries, total_count=total_count)
