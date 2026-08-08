"""PR-tier real-ingestion tests: durable submission verified against DB deltas.

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "Pull-request real-ingestion tier verifies durable results against
database deltas."

Each representative source is submitted through ``OperationService`` (the
canonical durable workflow), driven to a terminal state through the real worker
boundary, and its claimed result count is checked against the actual committed
``Content`` row delta. The tier runs offline against deterministic fixtures.
"""

from __future__ import annotations

import pytest

from tests.real_ingestion.harness import (
    PR_TIER_KEYS,
    assert_result_matches_delta,
)

pytestmark = [pytest.mark.real_ingest, pytest.mark.asyncio]


@pytest.mark.parametrize("key", PR_TIER_KEYS)
async def test_pr_tier_source_completes_and_matches_db_delta(
    real_ingestion_harness, key: str
) -> None:
    """A representative fixture ingestion completes and matches the DB delta."""

    outcome = await real_ingestion_harness.submit_fixture(key)

    assert outcome.status == "completed"
    assert_result_matches_delta(outcome)


async def test_pr_tier_persistence_mismatch_is_detected(real_ingestion_harness) -> None:
    """A terminal operation that under-persists is caught as a delta mismatch.

    We drive a real successful ingestion, then simulate the "claims results the
    database did not persist" failure by deleting the persisted row out from
    under the claimed result. The DB-delta helper must reject it rather than
    trust the operation's claim.
    """

    outcome = await real_ingestion_harness.submit_fixture("rss")
    assert outcome.succeeded
    assert outcome.claimed_content_ids

    # Persistence regression: the operation still claims a content row, but the
    # database no longer holds it.
    await real_ingestion_harness.cleanup()

    stale = await real_ingestion_harness.recount(outcome)
    assert stale.claimed_content_ids  # operation still claims a result
    assert stale.content_row_delta == 0  # ...but nothing is persisted
    with pytest.raises(AssertionError, match="database delta"):
        assert_result_matches_delta(stale)


async def test_obsidian_fixture_is_incremental_path_free_and_uses_real_adapter(
    real_ingestion_harness,
) -> None:
    """New -> unchanged -> changed clips match Content, event, and state deltas.

    The fixture vault holds four notes: two valid clips of distinct pages, one
    clip of a page a second note already covers (shared canonical URL), and one
    clip missing required metadata.
    """

    first = await real_ingestion_harness.submit_fixture("obsidian_vault")
    unchanged = await real_ingestion_harness.submit_fixture("obsidian_vault")
    real_ingestion_harness.change_obsidian_fixture()
    changed = await real_ingestion_harness.submit_fixture("obsidian_vault")

    # Three valid clips persist as three distinct rows, because each note keeps
    # its own annotations, and the invalid clip fails.
    assert first.status == "completed"
    assert first.content_row_delta == 3
    assert first.source_state_row_delta == 4
    assert first.source_event_row_delta == 4
    # ...but the two notes clipping one page resolve to a single canonical
    # primary, so the durable result claims two identities, not three rows.
    assert first.primary_identity_delta == 2
    assert set(first.claimed_content_ids) == set(first.persisted_primary_ids)
    assert len(first.persisted_content_ids) == 3

    # Re-observing an unchanged vault commits nothing at all.
    assert unchanged.content_row_delta == 0
    assert unchanged.source_state_row_delta == 0
    assert unchanged.source_event_row_delta == 0
    assert unchanged.claimed_content_ids == ()

    # A changed note is a new immutable file version: it adds one row that links
    # back to the primary its earlier version established.
    assert changed.status == "completed"
    assert changed.content_row_delta == 1
    assert changed.source_state_row_delta == 0
    assert changed.source_event_row_delta == 1
    assert changed.primary_identity_delta == 1
    assert set(changed.claimed_content_ids) == set(changed.persisted_primary_ids)
    assert set(changed.claimed_content_ids).isdisjoint(changed.persisted_content_ids)

    assert first.source_state_status_delta == {"failed": 1, "ingested": 3}
    assert first.source_event_status_delta == {"failed": 1, "ingested": 3}
    assert unchanged.source_state_status_delta == {}
    assert unchanged.source_event_status_delta == {}
    assert changed.source_state_status_delta == {}
    assert changed.source_event_status_delta == {"ingested": 1}
    assert first.source_state_attempt_delta == 4
    assert first.source_event_attempt_delta == 4
    # The invalid clip is re-attempted against its bounded retry budget even
    # when nothing else changed; no other note is touched.
    assert unchanged.source_state_attempt_delta == 1
    assert unchanged.source_event_attempt_delta == 1
    assert changed.source_state_attempt_delta == 1
    assert changed.source_event_attempt_delta == 2

    for outcome in (first, unchanged, changed):
        assert outcome.result is not None
        assert outcome.result["items_ingested"] == outcome.content_row_delta
        assert len(outcome.result["content_ids"]) == (outcome.primary_identity_delta or 0)
    assert first.result["items_failed"] == 1
    assert unchanged.result["items_skipped"] == 3
    assert unchanged.result["items_failed"] == 1
    assert changed.result["items_skipped"] == 2
    assert changed.result["items_failed"] == 1

    evidence = str((first.result, unchanged.result, changed.result))
    assert "missing_required_metadata" in evidence
    for private_value in (
        "vault_path",
        "ingest_folder",
        "fixture-vault",
        "valid.md",
        "invalid.md",
        "fixture.invalid",
        "source_url:",
    ):
        assert private_value not in evidence


async def test_obsidian_retained_failure_stops_failing_later_unchanged_scans(
    real_ingestion_harness,
) -> None:
    """A permanently invalid clip must not fail every future scan of the vault.

    The invalid clip is retried against its bounded budget and each of those
    attempts is a real failure. Once the budget is spent and the file has not
    changed, later scans attempt nothing, so the operation must reach a
    successful terminal state and restate the retained code as a warning —
    otherwise a single bad note alerts an operator on every poll forever.
    """

    outcomes = [await real_ingestion_harness.submit_fixture("obsidian_vault") for _ in range(6)]
    statuses = [outcome.status for outcome in outcomes]

    # Ingest, then the bounded retries, then convergence.
    assert statuses[0] == "completed"
    assert statuses[1:3] == ["failed", "failed"]
    assert statuses[3:] == ["completed", "completed", "completed"]

    for spent in outcomes[3:]:
        assert spent.result is not None
        assert spent.result["items_failed"] == 0
        assert spent.result["errors"] == []
        assert spent.result["items_skipped"] == 4
        assert spent.result["outcome"] == "zero_items"
        # The failure stays visible, and stays non-secret.
        assert [warning["code"] for warning in spent.result["warnings"]] == ["retry_exhausted"]
        assert spent.source_event_attempt_delta == 0
        assert spent.content_row_delta == 0
