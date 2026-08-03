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
    first = await real_ingestion_harness.submit_fixture("obsidian_vault")
    unchanged = await real_ingestion_harness.submit_fixture("obsidian_vault")
    real_ingestion_harness.change_obsidian_fixture()
    changed = await real_ingestion_harness.submit_fixture("obsidian_vault")

    assert first.status == "completed"
    assert first.content_row_delta == 3
    assert first.source_state_row_delta == 4
    assert first.source_event_row_delta == 4
    assert unchanged.content_row_delta == 0
    assert unchanged.source_state_row_delta == 0
    assert unchanged.source_event_row_delta == 0
    assert changed.content_row_delta == 1
    assert changed.source_state_row_delta == 0
    assert changed.source_event_row_delta == 1
    assert set(first.claimed_content_ids) == set(first.persisted_content_ids)
    assert set(unchanged.claimed_content_ids) == set(unchanged.persisted_content_ids)
    assert set(changed.claimed_content_ids) == set(changed.persisted_content_ids)
    assert first.source_state_status_delta == {"failed": 1, "ingested": 3}
    assert first.source_event_status_delta == {"failed": 1, "ingested": 3}
    assert unchanged.source_state_status_delta == {}
    assert unchanged.source_event_status_delta == {}
    assert changed.source_state_status_delta == {}
    assert changed.source_event_status_delta == {"ingested": 1}
    assert first.source_state_attempt_delta == 4
    assert first.source_event_attempt_delta == 4
    assert unchanged.source_state_attempt_delta == 0
    assert unchanged.source_event_attempt_delta == 0
    assert changed.source_state_attempt_delta == 0
    assert changed.source_event_attempt_delta == 1

    for outcome in (first, unchanged, changed):
        assert outcome.result is not None
        assert outcome.result["items_ingested"] == outcome.content_row_delta
        assert len(outcome.result["content_ids"]) == outcome.content_row_delta
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
