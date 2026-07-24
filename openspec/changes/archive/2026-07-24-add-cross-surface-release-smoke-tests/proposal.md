# Add cross-surface release smoke tests

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `add-cross-surface-release-smoke-tests`
> Effort: L
> Priority: 4

## Summary

Add an automated deployed-environment compatibility gate spanning the served
frontend, the installed `aca` CLI, and the canonical workflow API. The default
tier is production-safe and read-only. A separate, explicitly enabled staging
or ephemeral tier submits one canonical ingestion and follows its durable
operation. Both tiers emit sanitized, schema-validated evidence containing the
revisions actually observed at the network boundary.

## Dependencies

- `ri-01` — canonical CLI transport behavior
- `ri-02` — restored frontend release boundary and production evidence model

## Problem

Source and unit tests cannot prove which frontend bundle and API revision are
actually serving traffic. A stale PWA/CDN artifact can retain a retired
mutation, while a client can serialize an absent cursor as `cursor=` and fail
only against a strict deployed server. The current production verification is
manual and allows revision identity to be inferred from deployment metadata
instead of observed from the service.

## Scope

- Publish non-secret release revision metadata from the backend liveness
  endpoint and the built frontend document.
- Add a Python release-smoke runner with a production-safe default tier.
- Pin every credential-bearing request to exact origins and deployment identity
  supplied by an approval-protected environment policy; origins are never
  workflow inputs.
- Exercise capability and first-page discovery through direct HTTP, the real
  CLI subprocess, and a deployed Playwright browser session.
- Inspect every served first-party JavaScript asset and observed request for
  a non-overridable baseline of retired workflow mutations, using a
  revision-bound asset manifest emitted by Vite.
- Add an opt-in mutation tier restricted to declared staging or ephemeral
  targets, submitting exactly one canonical ingestion and polling its durable
  operation to a successful terminal state.
- Emit and validate a bounded, sanitized JSON evidence report.
- Add CI/configuration gates and an operator runbook for production read-only
  and staging mutation execution.

## Out of Scope

- Replacing the canonical workflow OpenAPI or generated clients.
- Mutating production as part of the automated smoke gate.
- Deploying services, managing Railway environments, or creating staging
  infrastructure.
- Broad real-adapter ingestion coverage; that belongs to `ri-05`.
- CLI semantic evaluation; that belongs to `ri-06`.

## Acceptance Outcomes

- The gate fails when the deployed frontend requests or contains a retired
  workflow mutation.
- The gate exercises capability discovery and first-page cursor omission
  through the frontend client and a real installed CLI process.
- A staging or ephemeral scenario submits exactly one canonical ingestion and
  observes its durable operation through successful completion.
- Default configuration and redundant runtime checks prevent every mutating
  scenario from targeting production.
- Promotion evidence records the frontend and API revisions observed from the
  served artifacts, verifies expected revisions when supplied, and contains no
  credentials, cookies, request headers, raw content, or natural identifiers.

## Risks

- A service worker or intermediary cache can hide the currently served
  frontend. The runner uses a fresh browser context with service workers
  blocked, cache-busting navigation, and direct asset retrieval.
- An ambiguous mutation response can lead to duplicate work. The mutation tier
  sends one request with an explicit idempotency key and never automatically
  retries submission.
- Evidence can leak production credentials or content. Secrets remain in
  environment variables, subprocess output is sanitized, and the evidence
  schema permits only opaque IDs, safe origins, revisions, statuses, counts,
  timestamps, and asset digests.
- A mislabeled target can exfiltrate credentials or mutate production. Release
  jobs take origins and deployment identity only from protected environment
  policy, reject redirects and production aliases, and attach credentials only
  after exact-origin validation.

## Approval

Approved through parent roadmap `roadmap-workflow-surface-reliability` on
2026-07-23.
