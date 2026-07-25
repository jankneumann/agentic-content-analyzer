"""Failure-class evidence tests for the real-ingestion tiers.

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "CI publishes failure-class evidence distinguishing adapter, queue,
and persistence failures."

The classifier is a pure function over the durable operation/result records — no
new run-state representation (design D2). Adapter diagnostics follow the real
``_ingestion_diagnostic`` format emitted by
``src/queue/workflow_handlers.py`` ("Ingestion '<src>' failed after N attempts").
"""

from __future__ import annotations

import pytest

from src.ingestion.real_ingest_evidence import (
    FailureClass,
    SourceEvidence,
    classify_source_outcome,
    render_failure_summary,
)

pytestmark = pytest.mark.real_ingest


def test_completed_matching_delta_is_success() -> None:
    result = classify_source_outcome(status="completed", claimed_content_ids=[11], content_delta=1)
    assert result is FailureClass.SUCCESS


def test_completed_but_underpersisted_is_persistence() -> None:
    """A terminal success claiming rows the DB did not persist is a persistence failure."""

    result = classify_source_outcome(status="completed", claimed_content_ids=[11], content_delta=0)
    assert result is FailureClass.PERSISTENCE


def test_adapter_error_is_not_misreported_as_persistence() -> None:
    """An upstream adapter failure with zero rows classifies as adapter, not persistence."""

    detail = "Ingestion 'rss' failed after 3 attempts (HTTP 429): too many requests"
    result = classify_source_outcome(
        status="failed",
        claimed_content_ids=[],
        content_delta=0,
        problem_detail=detail,
    )
    assert result is FailureClass.ADAPTER
    assert result is not FailureClass.PERSISTENCE


def test_recorded_db_write_error_is_persistence() -> None:
    detail = "Ingestion 'rss' failed to persist content: database write error"
    result = classify_source_outcome(
        status="failed",
        claimed_content_ids=[],
        content_delta=0,
        problem_detail=detail,
    )
    assert result is FailureClass.PERSISTENCE


def test_nonterminal_operation_is_queue_failure() -> None:
    """A job that never reached a terminal transition is a queue-layer failure."""

    for status in ("queued", "in_progress"):
        result = classify_source_outcome(status=status, claimed_content_ids=[], content_delta=0)
        assert result is FailureClass.QUEUE


def test_generic_terminal_failure_without_adapter_signature_is_queue() -> None:
    result = classify_source_outcome(
        status="failed",
        claimed_content_ids=[],
        content_delta=0,
        problem_detail="Job failed due to an internal error",
    )
    assert result is FailureClass.QUEUE


def test_summary_maps_each_failure_to_exactly_one_layer() -> None:
    evidence = [
        SourceEvidence("rss", "1", FailureClass.SUCCESS, claimed=1, delta=1, detail=None),
        SourceEvidence(
            "gmail",
            "2",
            FailureClass.ADAPTER,
            claimed=0,
            delta=0,
            detail="Ingestion 'gmail' failed after 3 attempts (HTTP 503)",
        ),
        SourceEvidence("url", "3", FailureClass.PERSISTENCE, claimed=1, delta=0, detail=None),
    ]

    summary = render_failure_summary(evidence)

    # Every non-successful source appears with exactly one classification.
    assert "gmail" in summary
    assert "adapter" in summary
    assert "url" in summary
    assert "persistence" in summary
    # A failing source is not double-classified.
    for line in summary.splitlines():
        if "gmail" in line:
            assert "persistence" not in line and "queue" not in line


def test_summary_reports_all_success_when_no_failures() -> None:
    evidence = [
        SourceEvidence("rss", "1", FailureClass.SUCCESS, claimed=1, delta=1, detail=None),
    ]
    summary = render_failure_summary(evidence)
    assert "1" in summary  # count of sources
    assert "adapter" not in summary.lower() or "0" in summary


@pytest.mark.asyncio
async def test_real_completed_operation_classifies_as_success(
    real_ingestion_harness,
) -> None:
    """Evidence for a real, committed ingestion is derived from its durable record."""

    outcome = await real_ingestion_harness.submit_fixture("rss")
    evidence = real_ingestion_harness.evidence(outcome)

    assert evidence.failure_class is FailureClass.SUCCESS
    assert evidence.operation_id == outcome.operation_id
    assert evidence.claimed == evidence.delta == 1

    summary = render_failure_summary([evidence])
    assert "success: 1" in summary
