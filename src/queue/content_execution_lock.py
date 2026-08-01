"""Shared transaction advisory lock for Content domain mutations."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_CONTENT_EXECUTION_LOCK_NAMESPACE = 1_380_108_301


def lock_content_transaction(session: Session, content_id: int) -> None:
    """Serialize one Content mutation for the current database transaction."""

    if content_id <= 0:
        raise ValueError("content_id must be positive")
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :content_id)"),
        {"namespace": _CONTENT_EXECUTION_LOCK_NAMESPACE, "content_id": content_id},
    )
