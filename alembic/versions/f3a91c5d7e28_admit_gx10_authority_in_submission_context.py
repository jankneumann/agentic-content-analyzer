"""Admit the GX-10 authority fields in the queue submission context.

``OperationContextEnvelope`` is a strict, closed contract: every field must be
present in the persisted JSON, and the CHECK constraint that guards
``pgqueuer_jobs.submission_context`` enforces exactly that key set. The GX-10
work added ``authority_fingerprint`` and ``ownership_epoch`` to the envelope
without widening the constraint, so once submissions started reaching the
column at all, every one of them was rejected:

    new row for relation "pgqueuer_jobs" violates check constraint
    "ck_pgqueuer_jobs_submission_context"

Widening the key list alone would let the two fields through unvalidated, so
each is checked the way the envelope declares it: a 64-character lowercase hex
fingerprint, and a non-negative epoch that fits in a signed 64-bit integer.

Revision ID: f3a91c5d7e28
Revises: e4b7c9d2a610
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3a91c5d7e28"
down_revision: str | None = "e4b7c9d2a610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENVELOPE_KEYS: tuple[str, ...] = (
    "schema_version",
    "operation_id",
    "root_operation_id",
    "parent_operation_id",
    "traceparent",
    "tracestate",
    "trace_id",
    "span_id",
    "claim_generation",
    "attempt_number",
    "entrypoint",
    "service_name",
    "service_instance_id",
    "environment",
    "release_revision",
    "stage",
    "resource_kind",
    "resource_key",
)
_AUTHORITY_KEYS: tuple[str, ...] = ("authority_fingerprint", "ownership_epoch")

_AUTHORITY_CHECKS = """
                    AND jsonb_typeof(submission_context->'authority_fingerprint')
                        IN ('string','null')
                    AND jsonb_typeof(submission_context->'ownership_epoch') IN ('string','null')
                    AND (
                        jsonb_typeof(submission_context->'authority_fingerprint') = 'null'
                        OR (submission_context->>'authority_fingerprint') ~ '^[0-9a-f]{64}$'
                    )
                    AND (
                        jsonb_typeof(submission_context->'ownership_epoch') = 'null'
                        OR ((submission_context->>'ownership_epoch') ~ '^(0|[1-9][0-9]{0,18})$'
                            AND (submission_context->>'ownership_epoch')::numeric
                                BETWEEN 0 AND 9223372036854775807)
                    )"""


def _constraint(keys: tuple[str, ...], authority_checks: str) -> str:
    """Render the submission-context constraint for one key set."""
    key_list = ",".join(f"'{key}'" for key in keys)
    return f"""
        ALTER TABLE pgqueuer_jobs
            ADD CONSTRAINT ck_pgqueuer_jobs_submission_context CHECK (
                submission_context IS NULL OR (
                    jsonb_typeof(submission_context) = 'object'
                    AND submission_context @> '{{"schema_version": 1}}'::jsonb
                    AND submission_context ?& ARRAY[{key_list}]
                    AND (submission_context - ARRAY[{key_list}]::text[]) = '{{}}'::jsonb
                    AND jsonb_typeof(submission_context->'operation_id') = 'string'
                    AND jsonb_typeof(submission_context->'root_operation_id') = 'string'
                    AND jsonb_typeof(submission_context->'parent_operation_id') IN ('string','null')
                    AND jsonb_typeof(submission_context->'traceparent') = 'string'
                    AND jsonb_typeof(submission_context->'tracestate') IN ('string','null')
                    AND jsonb_typeof(submission_context->'trace_id') = 'string'
                    AND jsonb_typeof(submission_context->'span_id') = 'string'
                    AND jsonb_typeof(submission_context->'claim_generation') = 'string'
                    AND jsonb_typeof(submission_context->'attempt_number') IN ('string','null')
                    AND jsonb_typeof(submission_context->'entrypoint') = 'string'
                    AND jsonb_typeof(submission_context->'service_name') = 'string'
                    AND jsonb_typeof(submission_context->'service_instance_id') = 'string'
                    AND jsonb_typeof(submission_context->'environment') = 'string'
                    AND jsonb_typeof(submission_context->'release_revision') = 'string'
                    AND jsonb_typeof(submission_context->'stage') IN ('string','null')
                    AND jsonb_typeof(submission_context->'resource_kind') IN ('string','null')
                    AND jsonb_typeof(submission_context->'resource_key') IN ('string','null')
                    AND (submission_context->>'operation_id') ~ '^[1-9][0-9]{{0,18}}$'
                    AND (submission_context->>'operation_id')::numeric
                        BETWEEN 1 AND 9223372036854775807
                    AND (submission_context->>'root_operation_id') ~ '^[1-9][0-9]{{0,18}}$'
                    AND (submission_context->>'root_operation_id')::numeric
                        BETWEEN 1 AND 9223372036854775807
                    AND (
                        jsonb_typeof(submission_context->'parent_operation_id') = 'null'
                        OR ((submission_context->>'parent_operation_id') ~ '^[1-9][0-9]{{0,18}}$'
                            AND (submission_context->>'parent_operation_id')::numeric
                                BETWEEN 1 AND 9223372036854775807)
                    )
                    AND (submission_context->>'claim_generation') ~ '^(0|[1-9][0-9]{{0,18}})$'
                    AND (submission_context->>'claim_generation')::numeric
                        BETWEEN 0 AND 9223372036854775806
                    AND (
                        jsonb_typeof(submission_context->'attempt_number') = 'null'
                        OR ((submission_context->>'attempt_number') ~ '^[1-9][0-9]{{0,18}}$'
                            AND (submission_context->>'attempt_number')::numeric
                                = (submission_context->>'claim_generation')::numeric + 1)
                    )
                    AND length(submission_context->>'entrypoint') BETWEEN 1 AND 160
                    AND length(submission_context->>'service_name') BETWEEN 1 AND 100
                    AND length(submission_context->>'service_instance_id') BETWEEN 1 AND 128
                    AND length(submission_context->>'environment') BETWEEN 1 AND 32
                    AND length(submission_context->>'release_revision') BETWEEN 1 AND 64{authority_checks}
                    AND octet_length(submission_context::text) <= 4096
                )
            )
    """


def upgrade() -> None:
    """Accept, and validate, the two authority fields the envelope carries."""
    op.execute("ALTER TABLE pgqueuer_jobs DROP CONSTRAINT ck_pgqueuer_jobs_submission_context")
    op.execute(_constraint(_ENVELOPE_KEYS + _AUTHORITY_KEYS, _AUTHORITY_CHECKS))


def downgrade() -> None:
    """Return to the key set that predates the GX-10 authority fields."""
    op.execute("UPDATE pgqueuer_jobs SET submission_context = NULL WHERE submission_context ?| "
               "ARRAY['authority_fingerprint','ownership_epoch']")
    op.execute("ALTER TABLE pgqueuer_jobs DROP CONSTRAINT ck_pgqueuer_jobs_submission_context")
    op.execute(_constraint(_ENVELOPE_KEYS, ""))
