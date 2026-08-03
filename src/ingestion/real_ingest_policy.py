"""Declarative live-adapter policy for the scheduled real-ingestion tier (D4).

This table is the single source of truth for which adapters may run live in the
scheduled CI tier, which credential gates each one, and which providers are never
live-eligible. It is consulted only by the scheduled tier; the pull-request tier
is always fixture-only.

Credential env-var names mirror the pydantic ``Settings`` fields in
``src/config/settings.py`` (uppercased). A source with more than one credential
name is satisfied when *any* is present (e.g. YouTube accepts a dedicated key or
the shared Google key).

Deliberately conservative choices:

- **Paid providers** (X/Grok, Perplexity) are never live-eligible — they are
  exercised only through their deterministic fixtures.
- **Audio transcription** (podcast) and **local uploads** (files) are fixture-only:
  the former incurs per-minute transcription cost with no dedicated live budget,
  the latter has no upstream to exercise. They are not "paid API" providers, so
  they are reported distinctly from the paid exclusion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class LiveDecision(StrEnum):
    """What the scheduled tier does with a source for a given environment."""

    LIVE = "live"
    SKIP_MISSING_CREDENTIAL = "skip_missing_credential"
    SKIP_SOURCE_UNAVAILABLE = "skip_source_unavailable"
    FIXTURE_ONLY_PAID = "fixture_only_paid"
    FIXTURE_ONLY_DISABLED = "fixture_only_disabled"
    FIXTURE_ONLY = "fixture_only"


@dataclass(frozen=True)
class LiveAdapterPolicy:
    """Per-source live eligibility, credential gate, retry, and paid exclusion."""

    key: str
    live_eligible: bool
    paid: bool = False
    credential_env_vars: tuple[str, ...] = ()
    max_attempts: int = 2
    reason: str = ""
    requires_worker_local_mount: bool = False


class LivePolicyRegistryError(RuntimeError):
    """Raised during collection when registry and live-policy keys drift."""


@dataclass(frozen=True)
class LiveEvaluation:
    """The resolved decision for one source, with an operator-facing reason."""

    key: str
    decision: LiveDecision
    reason: str
    policy: LiveAdapterPolicy = field(repr=False, default=None)  # type: ignore[assignment]


def _free(key: str) -> LiveAdapterPolicy:
    return LiveAdapterPolicy(key=key, live_eligible=True)


def _credentialed(key: str, *env_vars: str) -> LiveAdapterPolicy:
    return LiveAdapterPolicy(key=key, live_eligible=True, credential_env_vars=env_vars)


def _paid(key: str, *env_vars: str) -> LiveAdapterPolicy:
    return LiveAdapterPolicy(
        key=key,
        live_eligible=False,
        paid=True,
        credential_env_vars=env_vars,
        reason=f"{key} is a paid provider; exercised through its fixture only",
    )


def _fixture_only(key: str, reason: str) -> LiveAdapterPolicy:
    return LiveAdapterPolicy(key=key, live_eligible=False, reason=reason)


def _worker_local_mount(key: str) -> LiveAdapterPolicy:
    return LiveAdapterPolicy(
        key=key,
        live_eligible=True,
        requires_worker_local_mount=True,
    )


def assert_live_policy_registry_complete(
    registry_keys: set[str] | frozenset[str],
    policy_keys: set[str] | frozenset[str],
) -> None:
    """Fail collection with the exact missing or extra live-policy mappings."""

    missing = sorted(set(registry_keys) - set(policy_keys))
    extra = sorted(set(policy_keys) - set(registry_keys))
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise LivePolicyRegistryError(
            "Live adapter policy does not match executable registry: " + ", ".join(details)
        )


# One entry per SOURCE_REGISTRY source. Kept exhaustive by
# ``test_every_registry_source_has_a_policy``.
LIVE_ADAPTER_POLICIES: dict[str, LiveAdapterPolicy] = {
    # Free, no-key upstreams — run live with no secret.
    "rss": _free("rss"),
    "blog": _free("blog"),
    "substack": _free("substack"),
    "youtube_rss": _free("youtube_rss"),
    "url": _free("url"),
    "arxiv_search": _free("arxiv_search"),
    "arxiv_paper": _free("arxiv_paper"),
    "huggingface_papers": _free("huggingface_papers"),
    # Semantic Scholar works without a key (the key only raises rate limits), so
    # these run live without gating on SEMANTIC_SCHOLAR_API_KEY.
    "scholar_search": _free("scholar_search"),
    "scholar_paper": _free("scholar_paper"),
    "scholar_references": _free("scholar_references"),
    # Credentialed, non-paid — run live only when the required secret is present.
    "gmail": _credentialed("gmail", "GMAIL_OAUTH_TOKEN_JSON", "GMAIL_CREDENTIALS_JSON"),
    "youtube_playlist": _credentialed("youtube_playlist", "YOUTUBE_API_KEY", "GOOGLE_API_KEY"),
    "readwise": _credentialed("readwise", "READWISE_API_KEY"),
    # Paid providers — never live-eligible.
    "x_search": _paid("x_search", "XAI_API_KEY"),
    "perplexity_search": _paid("perplexity_search", "PERPLEXITY_API_KEY"),
    # Non-paid but fixture-only for cost / no-upstream reasons.
    "podcast": _fixture_only(
        "podcast", "audio transcription incurs per-minute cost; fixture-only for now"
    ),
    "files": _fixture_only("files", "local upload source has no live upstream to exercise"),
    "obsidian_vault": _worker_local_mount("obsidian_vault"),
}


def evaluate_live_adapter(
    key: str,
    *,
    live_enabled: bool,
    env: Mapping[str, str],
    worker_local_mount_ready: bool | None = None,
) -> LiveEvaluation:
    """Resolve one source's live decision for the given environment.

    Args:
        key: A ``SOURCE_REGISTRY`` source key.
        live_enabled: Whether live execution is turned on (``REAL_INGEST_LIVE``).
        env: The environment to read credentials from (e.g. ``os.environ``).
    """

    policy = LIVE_ADAPTER_POLICIES[key]

    if not live_enabled:
        return LiveEvaluation(
            key,
            LiveDecision.FIXTURE_ONLY_DISABLED,
            "Live execution disabled (REAL_INGEST_LIVE unset); running fixture only",
            policy,
        )
    if policy.paid:
        return LiveEvaluation(key, LiveDecision.FIXTURE_ONLY_PAID, policy.reason, policy)
    if not policy.live_eligible:
        return LiveEvaluation(key, LiveDecision.FIXTURE_ONLY, policy.reason, policy)
    if policy.requires_worker_local_mount and worker_local_mount_ready is not True:
        return LiveEvaluation(
            key,
            LiveDecision.SKIP_SOURCE_UNAVAILABLE,
            "Skipped: compatible worker-local mount is unavailable",
            policy,
        )
    if policy.credential_env_vars and not any(env.get(var) for var in policy.credential_env_vars):
        names = " or ".join(policy.credential_env_vars)
        return LiveEvaluation(
            key,
            LiveDecision.SKIP_MISSING_CREDENTIAL,
            f"Skipped: missing credential ({names})",
            policy,
        )
    return LiveEvaluation(key, LiveDecision.LIVE, f"{key} eligible for live execution", policy)
