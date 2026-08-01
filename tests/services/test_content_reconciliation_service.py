"""Pure decision-matrix tests for fail-closed Content reconciliation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.services.content_reconciliation_service import (
    CandidateSnapshot,
    ContentReconciliationClassifier,
    LockState,
)


def _candidate(**overrides) -> CandidateSnapshot:
    candidate = CandidateSnapshot(
        content_id=41,
        content_status="processing",
        owner_operation_id=901,
        owner_claim_generation=3,
        owner_phase="processing",
        owner_version=5,
        operation_id=901,
        operation_status="failed",
        operation_claim_generation=3,
        operation_claim_protocol_version=2,
        operation_retry_count=1,
        operation_cancel_requested=False,
        operation_force=False,
        operation_is_stale=True,
        matching_summary=False,
        mismatched_summary=False,
        extraction_succeeded=False,
        lock_state=LockState.NOT_CHECKED,
        revalidated=True,
    )
    return replace(candidate, **overrides)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (
            _candidate(
                operation_status="completed",
                matching_summary=True,
            ),
            ("project_completed", "summary_exists", "completed", "completed", 1),
        ),
        (
            _candidate(
                content_status="parsing",
                owner_phase="parsing",
                operation_status="completed",
                extraction_succeeded=True,
            ),
            ("project_parsed", "extraction_completed", "parsed", "completed", 1),
        ),
        (
            _candidate(
                content_status="failed",
                owner_phase="parsing",
                operation_status="completed",
            ),
            ("none", "completed_output_missing", "failed", "completed", 1),
        ),
        (
            _candidate(operation_status="completed"),
            ("none", "completed_output_missing", "processing", "completed", 1),
        ),
        (
            _candidate(operation_status="queued", operation_force=True),
            ("none", "active_operation", "processing", "queued", 1),
        ),
        (
            _candidate(operation_status="in_progress", operation_is_stale=False),
            ("none", "active_operation", "processing", "in_progress", 1),
        ),
        (
            _candidate(
                operation_status="in_progress",
                operation_is_stale=False,
                operation_cancel_requested=True,
            ),
            ("none", "cancellation_pending", "processing", "in_progress", 1),
        ),
        (
            _candidate(
                operation_status="in_progress",
                lock_state=LockState.CONTENDED,
            ),
            ("none", "execution_locked", "processing", "in_progress", 1),
        ),
        (
            _candidate(
                operation_status="in_progress",
                operation_cancel_requested=True,
                lock_state=LockState.ACQUIRED,
            ),
            (
                "cancel_restore_parsed",
                "cancellation_requested",
                "parsed",
                "cancelled",
                1,
            ),
        ),
        (
            _candidate(
                operation_status="in_progress",
                lock_state=LockState.ACQUIRED,
            ),
            ("retry_operation", "stale_operation", "failed", "queued", 2),
        ),
        (
            _candidate(
                operation_status="in_progress",
                lock_state=LockState.NOT_CHECKED,
            ),
            ("retry_operation", "stale_operation", "failed", "queued", 2),
        ),
        (
            _candidate(content_status="failed", operation_status="failed"),
            ("retry_operation", "failed_operation", "failed", "queued", 2),
        ),
        (
            _candidate(
                content_status="failed",
                operation_status="failed",
                operation_retry_count=3,
            ),
            ("none", "retry_budget_exhausted", "failed", "failed", 3),
        ),
        (
            _candidate(
                content_status="failed",
                operation_status="failed",
                operation_force=True,
            ),
            ("none", "forced_reprocessing", "failed", "failed", 1),
        ),
        (
            _candidate(operation_status="cancelled"),
            ("restore_parsed", "summarization_cancelled", "parsed", "cancelled", 1),
        ),
        (
            _candidate(
                content_status="failed",
                owner_phase="parsing",
                operation_status="cancelled",
            ),
            ("restore_pending", "extraction_cancelled", "pending", "cancelled", 1),
        ),
        (
            _candidate(
                operation_id=None,
                operation_status=None,
                operation_retry_count=None,
            ),
            ("none", "missing_operation", "processing", None, None),
        ),
        (
            _candidate(operation_claim_generation=4),
            ("none", "ownership_conflict", "processing", "failed", 1),
        ),
        (
            _candidate(operation_claim_protocol_version=1),
            ("none", "incompatible_worker", "processing", "failed", 1),
        ),
    ],
    ids=[
        "matching-summary-projects-completed",
        "successful-extraction-projects-parsed",
        "completed-parsing-owner-missing-output",
        "completed-processing-owner-missing-summary",
        "queued-owner-is-active",
        "fresh-in-progress-owner-is-active",
        "fresh-cancellation-remains-worker-owned",
        "stale-content-lock-is-contended",
        "abandoned-cancellation-is-finalized",
        "stale-in-progress-owner-is-retried-after-lock",
        "dry-run-proposes-stale-in-progress-retry-without-lock",
        "failed-owner-is-retried",
        "retry-budget-is-exhausted",
        "forced-reprocessing-is-never-retried",
        "cancelled-processing-owner-restores-parsed",
        "cancelled-parsing-owner-restores-pending",
        "retained-away-operation-is-missing",
        "generation-mismatch-conflicts",
        "legacy-protocol-is-incompatible",
    ],
)
def test_classifier_covers_the_closed_decision_matrix(
    candidate: CandidateSnapshot,
    expected: tuple[str, str, str, str | None, int | None],
) -> None:
    decision = ContentReconciliationClassifier(max_retries=3).classify(candidate)

    assert (
        decision.action,
        decision.reason,
        decision.content_status_after,
        decision.operation_status_after,
        decision.retry_count_after,
    ) == expected


def test_classifier_excludes_protected_content_before_owner_inference() -> None:
    classifier = ContentReconciliationClassifier(max_retries=3)

    assert (
        classifier.classify(
            _candidate(
                content_status="completed",
                operation_id=None,
                operation_status=None,
            )
        )
        is None
    )
    assert (
        classifier.classify(
            _candidate(
                content_status="filtered_out",
                operation_claim_generation=999,
            )
        )
        is None
    )


def test_classifier_precedence_is_owner_then_protocol_then_cancellation_force_output() -> None:
    classifier = ContentReconciliationClassifier(max_retries=3)

    ownership_conflict = classifier.classify(
        _candidate(
            operation_claim_generation=4,
            operation_claim_protocol_version=1,
            operation_cancel_requested=True,
            operation_force=True,
            matching_summary=True,
        )
    )
    assert ownership_conflict is not None
    assert ownership_conflict.reason == "ownership_conflict"

    incompatible = classifier.classify(
        _candidate(
            operation_claim_protocol_version=1,
            operation_cancel_requested=True,
            operation_force=True,
            matching_summary=True,
        )
    )
    assert incompatible is not None
    assert incompatible.reason == "incompatible_worker"

    cancellation = classifier.classify(
        _candidate(
            operation_status="in_progress",
            operation_cancel_requested=True,
            operation_force=True,
            matching_summary=True,
            lock_state=LockState.ACQUIRED,
        )
    )
    assert cancellation is not None
    assert cancellation.reason == "cancellation_requested"

    forced = classifier.classify(
        _candidate(
            operation_force=True,
            matching_summary=True,
        )
    )
    assert forced is not None
    assert forced.reason == "forced_reprocessing"


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate(operation_id=902),
        _candidate(owner_phase="parsing"),
    ],
    ids=["operation-id", "phase-status"],
)
def test_classifier_rejects_every_exact_owner_token_mismatch(
    candidate: CandidateSnapshot,
) -> None:
    decision = ContentReconciliationClassifier(max_retries=3).classify(candidate)

    assert decision is not None
    assert decision.action == "none"
    assert decision.reason == "ownership_conflict"


def test_classifier_reports_mismatched_summary_without_using_old_output() -> None:
    decision = ContentReconciliationClassifier(max_retries=3).classify(
        _candidate(
            operation_status="completed",
            mismatched_summary=True,
        )
    )

    assert decision is not None
    assert decision.action == "none"
    assert decision.reason == "output_owner_mismatch"


def test_classifier_reports_apply_revalidation_conflict_before_mutation() -> None:
    decision = ContentReconciliationClassifier(max_retries=3).classify(
        _candidate(revalidated=False)
    )

    assert decision is not None
    assert decision.action == "none"
    assert decision.reason == "revalidation_conflict"
