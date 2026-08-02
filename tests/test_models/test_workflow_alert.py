"""Model contract tests for workflow terminal evidence and alert delivery."""

from sqlalchemy import CheckConstraint

from src.models import WorkflowAlertDelivery, WorkflowTerminalEvent


def _checks(model: type[object]) -> dict[str, str]:
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_terminal_event_model_has_closed_shape_without_authority_foreign_keys() -> None:
    table = WorkflowTerminalEvent.__table__
    assert set(table.columns) == {
        table.c.id,
        table.c.event_key,
        table.c.source_kind,
        table.c.operation_id,
        table.c.claim_generation,
        table.c.terminal_status,
        table.c.reconciliation_action_id,
        table.c.reconciliation_run_id,
        table.c.reconciliation_content_id,
        table.c.classification_status,
        table.c.envelope,
        table.c.telemetry_emitted_at,
        table.c.occurred_at,
        table.c.created_at,
    }
    assert not table.foreign_keys
    assert table.c.event_key.unique is True
    assert "operation" in _checks(WorkflowTerminalEvent)["ck_workflow_terminal_events_source_kind"]
    assert ">= 0" in _checks(WorkflowTerminalEvent)["ck_workflow_terminal_events_claim_generation"]
    identity = _checks(WorkflowTerminalEvent)["ck_workflow_terminal_events_event_identity"]
    assert "operation_id" in identity
    assert "claim_generation" in identity
    assert "reconciliation_action_id" in identity
    assert "reconciliation_run_id" in identity
    assert "reconciliation_content_id" in identity


def test_delivery_model_has_only_restrict_event_fk_and_bounded_indexes() -> None:
    table = WorkflowAlertDelivery.__table__
    assert len(table.foreign_keys) == 1
    event_fk = next(iter(table.foreign_keys))
    assert event_fk.target_fullname == "workflow_terminal_events.id"
    assert event_fk.ondelete == "RESTRICT"
    checks = _checks(WorkflowAlertDelivery)
    assert "exhausted" in checks["ck_workflow_alert_deliveries_status"]
    state = checks["ck_workflow_alert_deliveries_state"]
    assert "attempt_count >= 1" in state
    assert "lease_expires_at IS NOT NULL" in state
    assert "delivered_at IS NOT NULL" in state
    assert "last_error_code IS NOT NULL" in state
    indexes = {index.name: index for index in table.indexes}
    pending = indexes["ix_workflow_alert_deliveries_pending_due"]
    assert [column.name for column in pending.columns] == ["next_attempt_at", "id"]
    assert str(pending.dialect_options["postgresql"]["where"]) == "status = 'pending'"
    leased = indexes["ix_workflow_alert_deliveries_lease_expiry"]
    assert [column.name for column in leased.columns] == ["lease_expires_at", "id"]
    assert str(leased.dialect_options["postgresql"]["where"]) == "status = 'leased'"
    assert "ix_workflow_alert_deliveries_retention" in indexes
