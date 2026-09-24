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
    result_diagnostic_codes,
)
from tests.real_ingestion.dead_session import (
    DEAD_SUBSTACK_COOKIE,
    dead_substack_session_orchestrator,
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


def test_database_integrity_error_is_persistence_not_adapter() -> None:
    """A real DB write failure carries the adapter prefix but is a persistence failure.

    ``_ingestion_diagnostic`` wraps *every* exception — including database errors —
    in the ``Ingestion '<src>' failed after N attempts (<TypeName>): <exc>`` format,
    so a ``IntegrityError`` (e.g. a duplicate-key violation) begins with the adapter
    prefix yet must be attributed to persistence, not the adapter. The classifier
    checks persistence signatures first for exactly this reason.
    """

    detail = (
        "Ingestion 'rss' failed after 1 attempt (IntegrityError): "
        "(psycopg2.errors.UniqueViolation) duplicate key value violates unique "
        'constraint "contents_source_id_key"'
    )
    result = classify_source_outcome(
        status="failed",
        claimed_content_ids=[],
        content_delta=0,
        problem_detail=detail,
    )
    assert result is FailureClass.PERSISTENCE
    assert result is not FailureClass.ADAPTER


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


def test_summary_records_skipped_credential_gaps() -> None:
    evidence = [
        SourceEvidence("rss", "1", FailureClass.SUCCESS, claimed=1, delta=1, detail=None),
        SourceEvidence(
            "gmail",
            "skipped",
            FailureClass.SKIPPED,
            claimed=0,
            delta=0,
            detail="Skipped: missing credential (GMAIL_OAUTH_TOKEN_JSON or GMAIL_CREDENTIALS_JSON)",
        ),
    ]
    summary = render_failure_summary(evidence)
    assert "skipped: 1" in summary
    assert "gmail" in summary
    assert "GMAIL_OAUTH_TOKEN_JSON" in summary


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


# -- credential-gated sources (ri-16) ------------------------------------------


def test_result_codes_are_read_from_every_diagnostic_list() -> None:
    result = {
        "errors": [{"code": "session_expired", "message": "m"}],
        "warnings": [{"code": "fetch_error", "message": "m"}],
        "source_outcomes": [
            {"errors": [{"code": "session_expired", "message": "m"}], "warnings": []},
            {"errors": [{"code": "not-a-public-code", "message": "m"}], "warnings": []},
        ],
    }

    assert result_diagnostic_codes(result) == ("session_expired", "fetch_error")
    assert result_diagnostic_codes(None) == ()
    assert result_diagnostic_codes({"errors": "garbage"}) == ()


@pytest.mark.parametrize(
    ("key", "code", "command"),
    [
        ("substack", "session_expired", "aca auth session substack"),
        ("substack", "credentials_missing", "aca auth session substack"),
        ("x_bookmarks", "session_expired", "aca auth session x"),
    ],
)
def test_summary_names_the_credential_code_and_its_refresh_command(
    key: str, code: str, command: str
) -> None:
    evidence = [
        SourceEvidence(
            key,
            "7",
            FailureClass.ADAPTER,
            claimed=0,
            delta=0,
            detail=f"Ingestion '{key}' failed",
            codes=(code,),
        )
    ]

    row = next(line for line in render_failure_summary(evidence).splitlines() if key in line)

    assert code in row
    assert f"`{command}`" in row


def test_summary_offers_no_refresh_command_for_an_ordinary_failure() -> None:
    evidence = [
        SourceEvidence(
            "substack",
            "7",
            FailureClass.ADAPTER,
            0,
            0,
            "Ingestion 'substack' failed",
            ("fetch_error",),
        )
    ]

    summary = render_failure_summary(evidence)

    assert "fetch_error" in summary
    assert "aca auth session" not in summary


@pytest.mark.asyncio
async def test_a_dead_substack_session_is_recorded_with_its_code(
    real_ingestion_harness,
) -> None:
    """The real adapter fails closed through the real durable workflow, and the
    evidence artifact says why and what to run — never the cookie."""

    outcome = await real_ingestion_harness.submit_with_orchestrator(
        "substack", dead_substack_session_orchestrator()
    )
    evidence = real_ingestion_harness.evidence(outcome)
    summary = render_failure_summary([evidence])

    assert outcome.status == "failed"
    assert outcome.content_row_delta == 0
    assert evidence.failure_class is FailureClass.ADAPTER
    assert evidence.codes == ("session_expired",)
    assert "session_expired (refresh: `aca auth session substack`)" in summary
    assert DEAD_SUBSTACK_COOKIE not in summary
    assert DEAD_SUBSTACK_COOKIE not in repr(outcome)
