# Tasks: Add cross-surface release smoke tests

> Change ID: `add-cross-surface-release-smoke-tests`
> Selected approach: observed revision metadata plus a two-tier deployed runner

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## Phase 1 — Served revision identity (`wp-release-identity`)

- [x] 1.1 Write backend liveness revision normalization and response tests. **(S)**
  **Spec scenarios:** Deployed revisions / Expected revisions match served revisions
  **Design decisions:** D1
- [x] 1.2 Publish an immutable full API revision and allowlisted provenance from
  `/health`; keep local diagnostics visibly non-promotable. **(S)**
  **Dependencies:** 1.1
- [x] 1.3 Write and test a detached-HEAD stamp generator plus frontend metadata
  selection for Railway/GitHub, CLI-upload without platform SHA, dirty/mismatch,
  missing, malformed, local, and spoofed revision sources. **(M)**
  **Design decisions:** D1
- [x] 1.4 Embed the selected frontend revision/provenance and emit a
  revision-bound manifest covering every JavaScript chunk. **(M)**
  **Dependencies:** 1.3
- [x] Checkpoint: run focused backend/frontend build-metadata tests and inspect
  production build output.

## Phase 2 — Read-only cross-surface runner (`wp-readonly-runner`)

- [x] 2.1 Define the explicit `release-smoke` dependency extra, protected target
  policy, exact-origin/redirect guards, result models, and revision comparison
  with production-safe defaults. **(M)**
  **Spec scenarios:** Default tier is read-only; Expected revisions match served revisions
  **Design decisions:** D2, D3
- [x] 2.2 Test and implement direct API discovery and real `aca` subprocess execution
  with environment-only credentials. **(M)**
  **Spec scenarios:** First discovery page omits cursor
  **Dependencies:** 2.1
- [x] 2.3 Add typed frontend configured-source discovery to the ingestion
  surface, with first-page cursor omission tests. **(M)**
  **Spec scenarios:** Frontend consumes capability discovery
  **Dependencies:** 2.1
- [x] 2.4 Test and implement deployed Playwright discovery using a fresh,
  service-worker-blocked context that rejects off-policy API traffic. **(M)**
  **Dependencies:** 2.3
- [x] 2.5 Define the non-overridable retired-route baseline and test/implement
  bounded manifest-complete asset plus normalized request scanning. **(L)**
  **Spec scenarios:** Browser observes a retired mutation; Served asset contains a retired mutation
  **Dependencies:** 1.4, 2.4
- [x] Checkpoint: run the read-only runner against a deterministic local fixture
  and verify no mutation method is emitted.

## Phase 3 — Guarded mutation and evidence (`wp-mutation-evidence`)

- [x] 3.1 Write fail-closed exact target identity, production alias,
  classification, and mutation-authorization tests. **(M)**
  **Spec scenarios:** Production mutation is rejected
  **Design decisions:** D4
- [x] 3.2 Define a checked-in, bounded, non-executable JSON fixture contract;
  implement one-shot canonical ingestion with run-ID-derived idempotency and
  successful terminal-state polling. **(M)**
  **Spec scenarios:** Staging mutation reaches successful terminal state
  **Dependencies:** 3.1
- [x] 3.3 Define the sanitized JSON evidence schema, conditional failure
  observations, provenance rules, and semantic validator. **(M)**
  **Spec scenarios:** Passing evidence is complete; Sensitive evidence is rejected
  **Design decisions:** D5
- [x] 3.4 Test pass, pre-observation failure, timeout, redaction,
  validator-failure envelope, and ambiguous-submit reconciliation paths. **(M)**
  **Dependencies:** 3.2, 3.3
- [x] Checkpoint: validate representative read-only and staging reports and run
  a secret-pattern scan over artifacts.

## Phase 4 — CI and operator integration (`wp-release-integration`)

- [ ] 4.1 Add production read-only and approval-controlled staging mutation workflow
  entry points whose target policy is protected and whose evidence is validated
  before retention. **(M)**
  **Spec scenarios:** Production promotion gate; Staging mutation workflow
  **Design decisions:** D6
- [ ] 4.2 Add deterministic configuration tests for workflow permissions, environment
  isolation, secret transport, expected revisions, and artifact retention. **(M)**
  **Dependencies:** 4.1
- [ ] 4.3 Document local, production read-only, and staging mutation commands plus
  detached-SHA stamp/upload identity, evidence interpretation, and failure
  handling in the canonical release runbook. **(M)**
  **Dependencies:** 2.4, 3.4, 4.2
- [ ] 4.4 Run focused Python, CLI, frontend, Playwright-fixture, configuration,
  schema, security, and strict OpenSpec gates. **(M)**
  **Dependencies:** 1.4, 2.5, 3.4, 4.3

## Gate 2 Approval

Approved through parent roadmap `roadmap-workflow-surface-reliability` on
2026-07-23. The plan forbids production mutation and requires revision identity
to be observed from served artifacts.
