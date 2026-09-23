"""PostgreSQL proof that ``aca auth status`` derives last_verified_at durably.

The browser-session rows read the completion time of the latest successful
ingestion from ``pgqueuer_jobs`` through ``OperationService``. This runs that
lookup against a real schema (built by ``alembic upgrade head``) inside a
rolled-back transaction, with a unique command key so other rows never count.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import asyncpg
import pytest

from src.cli import browser_session_status as bss

pytestmark = pytest.mark.integration

_KEY = "ri06_probe_substack"
_OTHER_KEY = "ri06_probe_never"


def _payload(command_key: str, outcome: str) -> str:
    return json.dumps(
        {
            "schema_version": 2,
            "operation_type": "ingestion.execute",
            "input": {"kind": command_key},
            "result": {
                "schema_version": 2,
                "command_key": command_key,
                "outcome": outcome,
                "items_ingested": 1 if outcome == "success" else 0,
                "items_skipped": 0,
                "items_failed": 1 if outcome in {"partial", "failed"} else 0,
                "source_outcomes": [],
            },
        }
    )


@pytest.mark.asyncio
async def test_last_verified_is_latest_successful_completion(test_engine) -> None:
    dsn = test_engine.url.render_as_string(hide_password=False)
    connection = await asyncpg.connect(dsn)
    transaction = connection.transaction()
    await transaction.start()
    try:
        rows = [
            ("completed", "success", datetime(2026, 9, 18, 3, 0, tzinfo=UTC)),
            ("completed", "zero_items", datetime(2026, 9, 19, 3, 0, tzinfo=UTC)),
            # Newer, but neither proves the session: excluded.
            ("completed", "partial", datetime(2026, 9, 20, 3, 0, tzinfo=UTC)),
            ("failed", "failed", datetime(2026, 9, 21, 3, 0, tzinfo=UTC)),
        ]
        for status, outcome, at in rows:
            await connection.execute(
                """
                INSERT INTO pgqueuer_jobs (entrypoint, payload, status, created_at, completed_at)
                VALUES ('ingestion.execute', $1::jsonb, $2, $3, $3)
                """,
                _payload(_KEY, outcome),
                status,
                at,
            )

        found = await bss._lookup_via_database_async([_KEY, _OTHER_KEY], connection)

        assert found == {_KEY: datetime(2026, 9, 19, 3, 0, tzinfo=UTC), _OTHER_KEY: None}
    finally:
        await transaction.rollback()
        await connection.close()
