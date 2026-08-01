"""Add measured compact ingestion-history indexes.

Revision ID: 7f4a2c9e1b60
Revises: 1e6a460b6722
Create Date: 2026-07-31 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "7f4a2c9e1b60"
down_revision: str | None = "1e6a460b6722"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INGESTION_OPERATION_SCOPE = """
(
    (
        jsonb_typeof(payload->'schema_version') = 'number'
        AND (payload->'schema_version')::text = '2'
        AND payload->>'operation_type' = 'ingestion.execute'
    )
    OR (
        NOT COALESCE(
            jsonb_typeof(payload->'schema_version') = 'number'
            AND (payload->'schema_version')::text = '2',
            FALSE
        )
        AND entrypoint IN ('ingest_content', 'extract_url_content')
    )
)
"""

_HISTORY_SCOPE = f"""
status IN ('completed', 'failed', 'cancelled')
AND {_INGESTION_OPERATION_SCOPE}
"""

_SOURCE_RESULT_SCOPE = f"""
jsonb_typeof(payload->'result'->'source_outcomes') = 'array'
AND {_INGESTION_OPERATION_SCOPE}
"""

_COMPACT_RESULT_ELIGIBLE = """
jsonb_typeof(payload->'result') = 'object'
AND jsonb_typeof(payload->'result'->'schema_version') = 'number'
AND (payload->'result'->'schema_version')::text = '2'
AND jsonb_typeof(payload->'result'->'command_key') = 'string'
AND payload->'result'->>'command_key' ~ '^[a-z][a-z0-9_]{0,99}$'
AND jsonb_typeof(payload->'result'->'outcome') = 'string'
AND payload->'result'->>'outcome' IN (
    'success', 'zero_items', 'partial', 'failed', 'cancelled', 'unknown'
)
AND jsonb_typeof(payload->'result'->'items_ingested') = 'number'
AND (payload->'result'->'items_ingested')::text ~ '^(0|[1-9][0-9]*)$'
AND jsonb_typeof(payload->'result'->'items_skipped') = 'number'
AND (payload->'result'->'items_skipped')::text ~ '^(0|[1-9][0-9]*)$'
AND jsonb_typeof(payload->'result'->'items_failed') = 'number'
AND (payload->'result'->'items_failed')::text ~ '^(0|[1-9][0-9]*)$'
AND jsonb_typeof(payload->'result'->'source_outcomes') = 'array'
"""

_COMMAND_EXPRESSION = f"""
CASE
    WHEN ({_COMPACT_RESULT_ELIGIBLE})
        THEN payload->'result'->>'command_key'
    WHEN jsonb_typeof(payload->'input'->'kind') = 'string'
     AND payload->'input'->>'kind' ~ '^[a-z][a-z0-9_]{{0,99}}$'
        THEN payload->'input'->>'kind'
    WHEN jsonb_typeof(payload->'source') = 'string'
     AND payload->>'source' ~ '^[a-z][a-z0-9_]{{0,99}}$'
        THEN payload->>'source'
    WHEN entrypoint = 'extract_url_content' THEN 'url'
    ELSE 'unknown'
END
"""

_OUTCOME_EXPRESSION = f"""
CASE
    WHEN status = 'failed' THEN 'failed'
    WHEN status = 'cancelled' THEN 'cancelled'
    WHEN ({_COMPACT_RESULT_ELIGIBLE})
        THEN payload->'result'->>'outcome'
    ELSE 'unknown'
END
"""


def upgrade() -> None:
    # The production queue is write-active. Build measured read indexes without
    # blocking operation submission or worker lifecycle updates.
    with op.get_context().autocommit_block():
        op.execute(  # noqa: S608 -- expressions and predicate are static migration SQL
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pgqueuer_jobs_history_order
            ON pgqueuer_jobs (created_at DESC, id DESC)
            WHERE {_HISTORY_SCOPE}
            """
        )
        op.execute(  # noqa: S608 -- expressions and predicate are static migration SQL
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pgqueuer_jobs_history_command_order
            ON pgqueuer_jobs (({_COMMAND_EXPRESSION}), created_at DESC, id DESC)
            WHERE {_HISTORY_SCOPE}
            """
        )
        op.execute(  # noqa: S608 -- expressions and predicate are static migration SQL
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pgqueuer_jobs_history_outcome_order
            ON pgqueuer_jobs (({_OUTCOME_EXPRESSION}), created_at DESC, id DESC)
            WHERE {_HISTORY_SCOPE}
            """
        )
        op.execute(  # noqa: S608 -- expressions and predicate are static migration SQL
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pgqueuer_jobs_history_source_keys
            ON pgqueuer_jobs USING GIN (
                (payload->'result'->'source_outcomes') jsonb_path_ops
            )
            WHERE {_SOURCE_RESULT_SCOPE}
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_pgqueuer_jobs_history_source_keys"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_pgqueuer_jobs_history_outcome_order"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_pgqueuer_jobs_history_command_order"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_pgqueuer_jobs_history_order")
