"""Live-tier real-ingestion tests (scheduled workflow).

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "Scheduled real-ingestion tier applies explicit live-adapter policy."

Two concerns are covered:

1. The *live drive path* (``submit_live`` — real registry, no fixture orchestrator)
   is exercised offline against a real adapter that fails fast with no credentials,
   verifying the durable operation still reaches a terminal state and the failure
   is classified into a layer. This needs no network success.
2. The *live network* half runs only when ``REAL_INGEST_LIVE`` is set (the
   scheduled workflow): each policy-permitted source is submitted live and must
   reach a terminal state, classified into the failure-class evidence.
"""

from __future__ import annotations

import os

import pytest

from src.ingestion.real_ingest_evidence import FailureClass
from src.ingestion.real_ingest_policy import (
    LIVE_ADAPTER_POLICIES,
    LiveDecision,
    evaluate_live_adapter,
)
from tests.fixtures.sources.library import SOURCE_FIXTURES
from tests.real_ingestion import evidence_sink

pytestmark = [pytest.mark.real_ingest, pytest.mark.asyncio]

_LIVE_ENABLED = os.environ.get("REAL_INGEST_LIVE", "0") not in {"", "0", "false", "False"}

# Every source the policy marks live-eligible and for which a command fixture
# exists to submit. Parametrizing from the policy (rather than the six PR keys)
# ensures no live-eligible adapter — substack, youtube_rss, arxiv_paper,
# huggingface_papers, the Scholar variants — is silently excluded from the live
# tier. The per-test guard still skips any source missing a credential in this
# environment, but the parametrization itself covers the full policy-permitted set.
LIVE_ELIGIBLE_KEYS = tuple(
    sorted(
        key
        for key, policy in LIVE_ADAPTER_POLICIES.items()
        if policy.live_eligible and key in SOURCE_FIXTURES
    )
)


async def test_live_drive_classifies_real_adapter_failure(real_ingestion_harness) -> None:
    """The real gmail adapter fails without credentials; the operation still terminates."""

    outcome = await real_ingestion_harness.submit_live("gmail")
    evidence = real_ingestion_harness.evidence(outcome)

    # A real adapter that cannot authenticate must not leave a dangling operation.
    assert outcome.status in {"completed", "failed"}
    if outcome.status == "failed":
        # A source/auth error is an adapter or queue-layer failure, never a lie
        # about persistence.
        assert evidence.failure_class in {FailureClass.ADAPTER, FailureClass.QUEUE}
        assert evidence.failure_class is not FailureClass.PERSISTENCE


@pytest.mark.skipif(not _LIVE_ENABLED, reason="live network tier runs only when REAL_INGEST_LIVE=1")
@pytest.mark.parametrize("key", LIVE_ELIGIBLE_KEYS)
async def test_live_source_reaches_terminal_state(real_ingestion_harness, key: str) -> None:
    """Each policy-permitted source submits live and reaches a classified terminal state."""

    decision = evaluate_live_adapter(key, live_enabled=True, env=os.environ)
    if decision.decision is not LiveDecision.LIVE:
        pytest.skip(decision.reason)

    outcome = await real_ingestion_harness.submit_live(key)
    evidence = real_ingestion_harness.evidence(outcome)
    evidence_sink.record(evidence)

    assert outcome.status in {"completed", "failed"}, outcome.problem_detail
    assert evidence.failure_class in set(FailureClass)
