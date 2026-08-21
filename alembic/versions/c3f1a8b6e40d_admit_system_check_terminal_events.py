"""Admit `system_check` rows in workflow_terminal_events.

Revision ID: c3f1a8b6e40d
Revises: b7d4f9a2c315
Create Date: 2026-08-21 00:00:00.000000

Why this migration exists at all
--------------------------------
The plan for this change originally claimed it added no migration, on the
reasoning that backup state lives in the backup target and so survives loss of
the database. That reasoning holds for backup *state*. It does not hold for
backup *alerting*.

The durable out-of-band alert path is anchored on ``workflow_terminal_events``,
whose three CHECK constraints reject a system-check row outright:

* ``ck_workflow_terminal_events_source_kind`` — a closed list of three kinds.
* ``ck_workflow_terminal_events_event_identity`` — an XOR over three exact
  ``event_key`` formulas, none of which a system check can satisfy.
* ``ck_workflow_terminal_events_source_shape`` — per-kind nullability of
  ``operation_id`` / ``claim_generation`` / ``terminal_status``, all of which a
  system check must leave NULL.

Without relaxing all three, the alert saying that backups are dead could have
been constructed in Pydantic and then never persisted — and the insert failure
would have surfaced as a rejected row, not as an error anybody saw. Widening one
or two of the three is no better than widening none: the row still does not
insert.

Rollback
--------
``downgrade()`` restores the original three-kind constraints, and deletes any
``system_check`` rows first — they cannot satisfy the restored constraints, so
leaving them would make the downgrade fail. Those rows are backup *alerts*, not
backup *data*: deleting them loses alert history, never a backup.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c3f1a8b6e40d"
down_revision: str | None = "b7d4f9a2c315"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SOURCE_KIND_WIDE = """
source_kind IN ('operation','reconciliation_action','reconciliation_failure','system_check')
"""

_SOURCE_KIND_NARROW = """
source_kind IN ('operation','reconciliation_action','reconciliation_failure')
"""

_EVENT_IDENTITY_RECONCILIATION = """
(source_kind = 'operation' AND event_key =
  'operation:' || operation_id::text || ':claim:' ||
  claim_generation::text || ':status:' || terminal_status)
OR
(source_kind = 'reconciliation_action' AND event_key =
  'reconciliation-action:' || reconciliation_action_id::text)
OR
(source_kind = 'reconciliation_failure' AND event_key =
  'reconciliation-failure:' || reconciliation_run_id::text || ':content:' ||
  reconciliation_content_id::text || ':reason:apply_failed'
 AND event_key ~
  '^reconciliation-failure:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:content:[1-9][0-9]*:reason:apply_failed$')
"""

# The one system-check grammar (design A2/A10). The suffix is the START of the
# fixed-length check window, so every evaluation inside one window derives the
# identical key — which is what makes the unique index on event_key deduplicate
# alerts per window instead of per worker tick.
_EVENT_IDENTITY_SYSTEM_CHECK = """
OR
(source_kind = 'system_check' AND event_key ~ '^system_check:backup_freshness:[0-9]+$')
"""

_SOURCE_SHAPE_RECONCILIATION = """
(source_kind = 'operation' AND operation_id IS NOT NULL
 AND claim_generation IS NOT NULL AND terminal_status IS NOT NULL
 AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL
 AND reconciliation_content_id IS NULL)
OR
(source_kind = 'reconciliation_action' AND operation_id IS NULL
 AND claim_generation IS NULL AND terminal_status IS NULL
 AND reconciliation_action_id IS NOT NULL AND reconciliation_run_id IS NOT NULL
 AND reconciliation_content_id IS NOT NULL)
OR
(source_kind = 'reconciliation_failure' AND operation_id IS NULL
 AND claim_generation IS NULL AND terminal_status IS NULL
 AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NOT NULL
 AND reconciliation_content_id IS NOT NULL)
"""

_SOURCE_SHAPE_SYSTEM_CHECK = """
OR
(source_kind = 'system_check' AND operation_id IS NULL
 AND claim_generation IS NULL AND terminal_status IS NULL
 AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL
 AND reconciliation_content_id IS NULL)
"""

_CONSTRAINTS = (
    "ck_workflow_terminal_events_source_kind",
    "ck_workflow_terminal_events_event_identity",
    "ck_workflow_terminal_events_source_shape",
)


def _replace(name: str, expression: str) -> None:
    op.execute(f"ALTER TABLE workflow_terminal_events DROP CONSTRAINT IF EXISTS {name}")
    op.execute(
        f"ALTER TABLE workflow_terminal_events ADD CONSTRAINT {name} CHECK ({expression})"
    )


def upgrade() -> None:
    """Relax all three constraints together."""

    _replace(_CONSTRAINTS[0], _SOURCE_KIND_WIDE)
    _replace(_CONSTRAINTS[1], _EVENT_IDENTITY_RECONCILIATION + _EVENT_IDENTITY_SYSTEM_CHECK)
    _replace(_CONSTRAINTS[2], _SOURCE_SHAPE_RECONCILIATION + _SOURCE_SHAPE_SYSTEM_CHECK)


def downgrade() -> None:
    """Restore the three-kind constraints, discarding system-check alert rows.

    The delete comes first and cascades to deliveries: a `system_check` row cannot
    satisfy the restored constraints, so a downgrade that left it in place would
    fail at constraint validation. What is lost is backup alert history — never a
    backup, and never any application data.
    """

    op.execute(
        "DELETE FROM workflow_alert_deliveries WHERE event_id IN "
        "(SELECT id FROM workflow_terminal_events WHERE source_kind = 'system_check')"
    )
    op.execute("DELETE FROM workflow_terminal_events WHERE source_kind = 'system_check'")

    _replace(_CONSTRAINTS[0], _SOURCE_KIND_NARROW)
    _replace(_CONSTRAINTS[1], _EVENT_IDENTITY_RECONCILIATION)
    _replace(_CONSTRAINTS[2], _SOURCE_SHAPE_RECONCILIATION)
