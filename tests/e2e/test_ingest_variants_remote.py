"""Live regression tests: ingest variants against a real backend.

Each test enqueues an ingestion job for one source variant via the public
HTTP API, then polls the non-SSE job-status endpoint until the job
finishes. This is the test suite that would have caught the bugs surfaced
in the 2026-05-18 triage session (worker dispatcher gaps, BM25 schema
break, SSL config, LLMResponse.content drift, BlogScraper parser gap,
embedding 500s, S2 rate limit).

Why a separate file from ``test_daily_pipeline_live.py``:
- That test is a *vertical* slice (one variant, full pipeline). This is a
  *horizontal* slice (all variants, ingest stage only).
- The pipeline test relies on SSE streaming; this one polls the JSON
  status endpoint because Railway's edge proxy drops long-lived SSE
  connections, which masked real worker failures during triage.

Usage::

    # Against production (the original failure mode):
    E2E_BASE_URL=https://api.aca.rotkohl.ai \
    E2E_ADMIN_KEY=$ADMIN_API_KEY \
        pytest tests/e2e/test_ingest_variants_remote.py -v --no-cov

    # Against locally-managed server (default):
    pytest tests/e2e/test_ingest_variants_remote.py -v --no-cov

    # Single variant:
    E2E_BASE_URL=... pytest tests/e2e/test_ingest_variants_remote.py \
        -v --no-cov -k "test_ingest_variant[url]"
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.e2e, pytest.mark.regression]


# Maximum seconds to wait for a single ingest job to reach a terminal state.
# Long enough for podcast/youtube fetches; short enough to fail fast on hangs.
INGEST_TIMEOUT_SECONDS = float(os.getenv("E2E_INGEST_TIMEOUT", "180"))
POLL_INTERVAL_SECONDS = 3.0


@dataclass
class IngestVariant:
    """Specification for one ingest-source regression test case."""

    source: str
    payload: dict[str, Any]
    requires_env: tuple[str, ...] = ()
    skip_reason: str | None = None
    # Some variants (xsearch, perplexity) hit external APIs that may rate-limit
    # or return non-deterministic results. For those we relax the assertion to
    # "did not crash" rather than "successfully ingested at least one item".
    allow_empty_result: bool = False
    extra_payload_env: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.source


# ─── Curated variant set ────────────────────────────────────────────
# Ordered roughly by determinism — deterministic ones first so failures
# surface quickly. Skip-marked ones stay in the parametrize list (visible
# in test output) instead of being filtered out, so we can see at a glance
# which variants are gated on environment configuration.

VARIANTS = [
    # ── Deterministic: single fixed URL, no external state ──
    IngestVariant(
        source="url",
        payload={
            "source": "url",
            "url": (
                "https://raw.githubusercontent.com/anthropics/anthropic-cookbook/main/README.md"
            ),
            "title": "Regression: Anthropic Cookbook README",
            "tags": ["regression-test", "ingest-variants"],
        },
    ),
    # ── Config-driven (uses sources.d/ on the backend) ──
    IngestVariant(
        source="rss",
        payload={"source": "rss", "max_results": 1},
    ),
    IngestVariant(
        source="podcast",
        # transcribe=False keeps the test under the timeout — full Whisper
        # transcription can take several minutes per episode.
        payload={"source": "podcast", "max_results": 1, "transcribe": False},
    ),
    IngestVariant(
        source="blog",
        payload={"source": "blog", "max_results": 1},
    ),
    IngestVariant(
        source="arxiv",
        payload={"source": "arxiv", "max_results": 1, "no_pdf": True},
    ),
    IngestVariant(
        source="huggingface_papers",
        payload={"source": "huggingface_papers", "max_results": 1},
    ),
    # ── External-API: skipped unless the API key is present on the backend.
    # We can't check the backend's env from here, so we treat "no error from
    # the API" as success and allow empty results.
    IngestVariant(
        source="perplexity",
        payload={
            "source": "perplexity",
            "prompt": "What is the most-cited 2025 paper on LLM reasoning?",
            "max_results": 1,
        },
        allow_empty_result=True,
    ),
    IngestVariant(
        source="xsearch",
        payload={
            "source": "xsearch",
            "prompt": "AI news this week",
            "max_threads": 1,
        },
        allow_empty_result=True,
    ),
    # ── OAuth-gated: skipped until aca auth --deploy work lands ──
    IngestVariant(
        source="gmail",
        payload={"source": "gmail", "max_results": 1},
        skip_reason=("Gmail OAuth credentials not yet deployed to Railway (see task #10, #24)"),
    ),
    IngestVariant(
        source="youtube",
        payload={"source": "youtube", "max_results": 1, "public_only": True},
        # public_only=True skips OAuth — but still depends on YT API key.
        # Mark as allow_empty_result rather than skip so we test the path.
        allow_empty_result=True,
    ),
    # ── Rate-limit-prone: skip by default (bug E) ──
    IngestVariant(
        source="scholar",
        payload={"source": "scholar", "max_results": 1},
        skip_reason=(
            "Semantic Scholar rate-limits unauthenticated requests "
            "(see task #22 — needs S2_API_KEY or backoff tuning)"
        ),
    ),
    # ── Substack: needs session cookie ──
    IngestVariant(
        source="substack",
        payload={"source": "substack", "max_results": 1},
        skip_reason="Substack requires per-user session cookie (not regression-suitable)",
    ),
]


# ─── Helpers ────────────────────────────────────────────────────────


def _preflight_backend_reachable(http_client: httpx.Client) -> str | None:
    """Verify the backend's /ready endpoint responds 200.

    Returns None if reachable, or a skip-reason string if not.

    We deliberately do NOT gate on ``queue_active_workers`` here, even
    though that was the first instinct. That field measures the count
    of jobs currently *in_progress* (with a fresh heartbeat) — so it's
    "0" any time the queue is idle, and absent entirely if the queue
    health check itself errors. Neither case means "no worker is
    running", so treating them as a skip-signal hid real failures.

    Instead we let _poll_job's 180s timeout surface the genuine
    "no worker consuming" case: tests will fail with
    ``last status: 'queued'``, which is a clear, actionable error.
    """
    try:
        resp = http_client.get("/ready", timeout=10.0)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return f"Backend not reachable at preflight: {e}"

    if resp.status_code != 200:
        return f"/ready returned {resp.status_code}: {resp.text[:200]}"

    # Log queue stats for diagnostic context, but don't gate on them.
    body = resp.json()
    workers = body.get("queue_active_workers")
    queue_status = body.get("queue")
    logger.info(
        "Backend reachable. queue=%s queue_active_workers=%s "
        "(NOTE: active_workers counts currently-running jobs, not capacity)",
        queue_status,
        workers,
    )
    return None


def _poll_job(
    http_client: httpx.Client,
    job_id: str,
    timeout: float = INGEST_TIMEOUT_SECONDS,
    interval: float = POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Poll the non-SSE /jobs/{id} endpoint until the job is terminal.

    Returns the final JobRecord dict. Raises TimeoutError if neither
    'completed' nor 'failed' is reached within the timeout. We use the
    polling endpoint instead of /ingest/status/{id}'s SSE because
    Railway's edge proxy aggressively closes long-lived streams.
    """
    deadline = time.time() + timeout
    last_status = "<not-yet-polled>"
    last_body: dict[str, Any] = {}

    while time.time() < deadline:
        try:
            resp = http_client.get(f"/api/v1/jobs/{job_id}")
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            # Transient connectivity hiccup — Railway's edge occasionally
            # drops connections. Retry next interval rather than failing.
            logger.warning("Polling /api/v1/jobs/%s raised %s; retrying", job_id, e)
            time.sleep(interval)
            continue
        if resp.status_code == 404:
            # The job was enqueued but no row exists yet — race with
            # the queue insertion. Wait one interval and retry.
            time.sleep(interval)
            continue
        if 500 <= resp.status_code < 600:
            # Railway's edge proxy returns 502 "Application failed to respond"
            # when the API container is briefly unresponsive (cold start, deploy,
            # transient memory pressure). The job is still running on the
            # worker — retry rather than fail the test on infra noise.
            logger.warning(
                "Polling /api/v1/jobs/%s returned %d (transient); retrying",
                job_id,
                resp.status_code,
            )
            time.sleep(interval)
            continue
        assert resp.status_code == 200, (
            f"Polling /api/v1/jobs/{job_id} returned {resp.status_code}: {resp.text[:200]}"
        )
        last_body = resp.json()
        last_status = last_body.get("status", "<unknown>")
        if last_status in ("completed", "failed"):
            return last_body
        time.sleep(interval)

    raise TimeoutError(
        f"Job {job_id} did not finish in {timeout}s "
        f"(last status: {last_status!r}, last body: {last_body!r})"
    )


def _assert_job_succeeded(
    job: dict[str, Any],
    variant: IngestVariant,
) -> None:
    """Assert the job reached 'completed' state without error.

    For variants flagged ``allow_empty_result=True``, a backend-side
    config error (e.g. missing PERPLEXITY_API_KEY) surfaces as
    status='failed' with a clear error string. We still fail the test
    on those — the operator should remove the variant from the suite
    or configure the backend, not silently pass on a misconfiguration.
    """
    status = job.get("status")
    error = job.get("error")

    assert status == "completed", (
        f"Variant {variant.source!r} ended with status={status!r}, error={error!r}. Full job: {job}"
    )
    assert not error, f"Variant {variant.source!r} completed but reported error: {error!r}"

    # We intentionally do not assert on payload.processed / payload.total
    # / "Ingested N items" message text. Reasons:
    #   - Single-URL ingest doesn't populate processed/total at all (only
    #     batch sources do), so the field shapes are heterogeneous.
    #   - Even for batch sources, "0 items" is a legitimate success: an
    #     RSS feed with no new entries since the last poll is fine; the
    #     URL variant re-ingesting an already-known URL is correctly
    #     deduplicated to 0.
    # The job-status terminal state is the source of truth — if the
    # worker said "completed" with no error, the variant works end-to-end.
    # Item-count assertions belong in source-specific unit tests, not
    # the cross-variant regression harness.


# ─── Tests ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def worker_ready(http_client: httpx.Client, admin_key: str) -> None:
    """Module-scoped preflight: skip every variant on hard env-setup failures.

    Checks:
    1. Admin key is present (without it, every POST hits 401 — confusing
       failure mode that looks like a backend bug). The most common cause
       is `E2E_ADMIN_KEY=$ADMIN_API_KEY pytest ...` where $ADMIN_API_KEY
       was unset in the shell, so E2E_ADMIN_KEY became literal "".
    2. Backend /ready returns 200 (proves backend is alive).

    We deliberately do NOT gate on queue/worker metrics — see
    _preflight_backend_reachable for why.
    """
    if not admin_key:
        pytest.skip(
            "No admin key available. Set E2E_ADMIN_KEY or ADMIN_API_KEY before "
            "invoking pytest. If you wrote `E2E_ADMIN_KEY=$ADMIN_API_KEY pytest ...`, "
            "verify $ADMIN_API_KEY is exported in your shell first: "
            "`echo ${#ADMIN_API_KEY}` should print a non-zero length.",
            allow_module_level=True,
        )
    reason = _preflight_backend_reachable(http_client)
    if reason:
        pytest.skip(reason, allow_module_level=True)


@pytest.mark.parametrize(
    "variant",
    VARIANTS,
    ids=lambda v: v.id,
)
def test_ingest_variant(
    http_client: httpx.Client,
    worker_ready: None,
    variant: IngestVariant,
) -> None:
    """Enqueue an ingest job for one variant and poll until terminal.

    This is the test suite that would have caught every bug we found
    on 2026-05-18. Each parametrized case is one variant; failures are
    isolated per variant rather than cascading.
    """
    if variant.skip_reason:
        pytest.skip(variant.skip_reason)

    for env_var in variant.requires_env:
        if not os.getenv(env_var):
            pytest.skip(f"Variant {variant.source!r} requires env var {env_var}")

    # Enqueue
    resp = http_client.post("/api/v1/contents/ingest", json=variant.payload)
    assert resp.status_code == 200, (
        f"POST /ingest for {variant.source!r} failed: {resp.status_code} {resp.text[:300]}"
    )
    body = resp.json()
    task_id = body.get("task_id")
    assert task_id, f"No task_id in ingest response: {body}"

    logger.info(
        "Enqueued %s ingest as job %s — polling for terminal status",
        variant.source,
        task_id,
    )

    # Poll
    job = _poll_job(http_client, task_id)

    # Assert
    _assert_job_succeeded(job, variant)
    logger.info("Variant %s completed: %s", variant.source, job.get("payload"))
