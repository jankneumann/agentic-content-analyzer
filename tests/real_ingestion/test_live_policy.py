"""Live-adapter policy tests for the scheduled real-ingestion tier.

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "Scheduled real-ingestion tier applies explicit live-adapter policy."

The policy table (design D4) is the single source of truth for which adapters may
run live, which credential gates them, and which paid APIs are never live-eligible.
Credential env-var names match ``src/config/settings.py``.
"""

from __future__ import annotations

import pytest

from src.ingestion.real_ingest_policy import (
    LIVE_ADAPTER_POLICIES,
    LiveDecision,
    evaluate_live_adapter,
)
from src.ingestion.registry import SOURCE_REGISTRY

pytestmark = pytest.mark.real_ingest


def test_every_registry_source_has_a_policy() -> None:
    """No executable source may be missing an explicit live decision."""

    assert set(LIVE_ADAPTER_POLICIES) == set(SOURCE_REGISTRY.keys())


def test_credentialed_source_runs_live_when_secret_present() -> None:
    evaluation = evaluate_live_adapter(
        "gmail", live_enabled=True, env={"GMAIL_OAUTH_TOKEN_JSON": "{...}"}
    )
    assert evaluation.decision is LiveDecision.LIVE


def test_credentialed_source_skips_with_reason_when_secret_absent() -> None:
    evaluation = evaluate_live_adapter("gmail", live_enabled=True, env={})
    assert evaluation.decision is LiveDecision.SKIP_MISSING_CREDENTIAL
    # The reason names the missing credential so operators can act on it.
    assert "GMAIL_OAUTH_TOKEN_JSON" in evaluation.reason


def test_youtube_accepts_either_api_key_or_google_key() -> None:
    with_youtube = evaluate_live_adapter(
        "youtube_playlist", live_enabled=True, env={"YOUTUBE_API_KEY": "k"}
    )
    with_google = evaluate_live_adapter(
        "youtube_playlist", live_enabled=True, env={"GOOGLE_API_KEY": "k"}
    )
    absent = evaluate_live_adapter("youtube_playlist", live_enabled=True, env={})
    assert with_youtube.decision is LiveDecision.LIVE
    assert with_google.decision is LiveDecision.LIVE
    assert absent.decision is LiveDecision.SKIP_MISSING_CREDENTIAL


@pytest.mark.parametrize("key", ["x_search", "perplexity_search"])
def test_paid_api_is_never_live_even_with_credentials(key: str) -> None:
    """Paid providers are fixture-only regardless of secrets or the live flag."""

    policy = LIVE_ADAPTER_POLICIES[key]
    assert policy.paid is True
    assert policy.live_eligible is False

    evaluation = evaluate_live_adapter(
        key,
        live_enabled=True,
        env={"XAI_API_KEY": "k", "PERPLEXITY_API_KEY": "k"},
    )
    assert evaluation.decision is LiveDecision.FIXTURE_ONLY_PAID


def test_free_no_key_source_runs_live() -> None:
    evaluation = evaluate_live_adapter("rss", live_enabled=True, env={})
    assert evaluation.decision is LiveDecision.LIVE


def test_live_disabled_forces_fixture_only_for_all() -> None:
    for key in SOURCE_REGISTRY.keys():
        evaluation = evaluate_live_adapter(key, live_enabled=False, env={})
        assert evaluation.decision is LiveDecision.FIXTURE_ONLY_DISABLED


def test_no_paid_source_is_live_eligible() -> None:
    for policy in LIVE_ADAPTER_POLICIES.values():
        if policy.paid:
            assert not policy.live_eligible, f"Paid source {policy.key} must not be live-eligible"
