"""Scheduled-tier real-ingestion tests (offline manifestation).

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "Scheduled real-ingestion tier applies explicit live-adapter policy."

The scheduled tier runs *every* fixture-backed source and, when
``REAL_INGEST_LIVE`` is set, additionally exercises the policy-permitted live
adapters. This module verifies the always-runnable, offline half: with live
execution disabled, every registry source is driven through the canonical
durable workflow against its deterministic fixture, matches its DB delta, and is
classified into the failure-class evidence summary. The live half runs only in
the scheduled CI workflow (Phase 5.3), gated per-secret by the policy table.
"""

from __future__ import annotations

import os

import pytest

from src.ingestion.real_ingest_evidence import FailureClass, render_failure_summary
from src.ingestion.real_ingest_policy import LiveDecision, evaluate_live_adapter
from src.ingestion.registry import SOURCE_REGISTRY
from tests.fixtures.sources.library import SOURCE_FIXTURES
from tests.real_ingestion import evidence_sink

pytestmark = [pytest.mark.real_ingest, pytest.mark.asyncio]

# The full fixture-backed set the scheduled tier covers.
SCHEDULED_KEYS = tuple(sorted(set(SOURCE_REGISTRY.keys()) & set(SOURCE_FIXTURES)))


def _live_enabled() -> bool:
    return os.environ.get("REAL_INGEST_LIVE", "0") not in {"", "0", "false", "False"}


@pytest.mark.parametrize("key", SCHEDULED_KEYS)
async def test_scheduled_source_fixture_completes_and_classifies(
    real_ingestion_harness, key: str
) -> None:
    """Every fixture-backed source completes offline and classifies as success."""

    decision = evaluate_live_adapter(key, live_enabled=_live_enabled(), env=os.environ)
    if decision.decision is LiveDecision.LIVE:
        pytest.skip(f"{key} is live-eligible in this environment; covered by the live tier")

    outcome = await real_ingestion_harness.submit_fixture(key)
    evidence = real_ingestion_harness.evidence(outcome)
    evidence_sink.record(evidence)

    assert outcome.status == "completed", f"{key}: {outcome.problem_detail}"
    assert evidence.failure_class is FailureClass.SUCCESS
    assert evidence.claimed == evidence.delta >= 1


async def test_scheduled_run_renders_failure_class_summary(real_ingestion_harness) -> None:
    """A scheduled run over several sources renders a per-source evidence summary."""

    sample = [k for k in ("rss", "url", "arxiv_search", "blog") if k in SOURCE_FIXTURES]
    evidence = []
    for key in sample:
        outcome = await real_ingestion_harness.submit_fixture(key)
        evidence.append(real_ingestion_harness.evidence(outcome))

    summary = render_failure_summary(evidence)
    assert f"success: {len(sample)}" in summary
    assert all(item.failure_class is FailureClass.SUCCESS for item in evidence)
