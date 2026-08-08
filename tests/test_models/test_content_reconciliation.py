"""Model contracts for persisted content reconciliation ownership."""

from __future__ import annotations

from src.models.content import Content
from src.models.content_reconciliation import ContentReconciliationAction
from src.models.jobs import JobRecord
from src.models.summary import Summary


def test_content_and_summary_expose_complete_owner_tokens() -> None:
    assert {
        "status_operation_id",
        "status_claim_generation",
        "status_operation_phase",
        "status_owner_version",
    } <= set(Content.__table__.columns.keys())
    assert {"operation_id", "operation_claim_generation"} <= set(Summary.__table__.columns.keys())

    content_constraints = {constraint.name for constraint in Content.__table__.constraints}
    summary_constraints = {constraint.name for constraint in Summary.__table__.constraints}
    assert "ck_contents_status_owner_complete" in content_constraints
    assert "ck_summaries_operation_owner_complete" in summary_constraints


def test_reconciliation_action_model_is_closed_and_has_no_destructive_foreign_keys() -> None:
    table = ContentReconciliationAction.__table__
    assert table.name == "content_reconciliation_actions"
    assert not table.foreign_keys
    assert {
        "run_id",
        "content_id",
        "operation_id",
        "claim_generation",
        "claim_protocol_version",
        "phase",
        "content_status_before",
        "content_status_after",
        "operation_status_before",
        "operation_status_after",
        "retry_count_before",
        "retry_count_after",
        "action",
        "reason",
        "created_at",
    } <= set(table.columns.keys())

    constraints = {constraint.name for constraint in table.constraints}
    assert {
        "uq_content_reconciliation_actions_run_content",
        "ck_content_reconciliation_action",
        "ck_content_reconciliation_reason",
    } <= constraints


def test_job_record_preserves_legacy_projection_defaults() -> None:
    fields = JobRecord.model_fields
    assert fields["claim_generation"].default == 0
    assert fields["claim_protocol_version"].default == 1
