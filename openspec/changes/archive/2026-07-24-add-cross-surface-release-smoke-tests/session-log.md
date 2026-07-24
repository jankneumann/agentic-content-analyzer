# Session Log: add-cross-surface-release-smoke-tests

## 2026-07-23 — Planning

- Confirmed RI-01 and RI-02 dependencies are complete.
- Inspected the canonical workflow client, real CLI command construction,
  frontend API client, Playwright setup, authentication boundary, health
  endpoint, CI, and production deployment runbook.
- Selected observed served revision metadata instead of operator-only revision
  labels.
- Split the gate into a production-safe read-only tier and a redundantly guarded
  staging/ephemeral mutation tier.
- Defined strict evidence minimization and retired-asset scanning requirements.
- Next gate: strict OpenSpec/package validation and independent plan review.

## 2026-07-23 — Independent plan review rework

- Resolved 3 blocker and 7 should-fix findings.
- Pinned credential-bearing traffic to approval-protected exact origins and
  target identity with redirect and production-alias rejection.
- Added real frontend configured-source discovery to implementation scope.
- Reordered evidence handling so validation always precedes upload.
- Made failure observations conditional, promotion revisions immutable and
  provenance-bound, and retired-route policy non-overridable.
- Defined a complete Vite asset manifest with count/byte/deadline bounds.
- Selected an explicit Python browser/schema extra, safe checked-in JSON
  fixtures, and run-ID-derived mutation idempotency.
- Re-review found the detached Railway CLI upload lacks platform commit metadata;
  added a clean-HEAD-verified build stamp, runbook scope, and stamp evidence
  tests rather than relying on a runtime override.
- Added focused frontend contract, typecheck, and build verification directly
  to the frontend-changing package.
- Independent final re-review signed off clean with strict OpenSpec, package
  schema/dependency/DAG/lock, command-availability, and diff checks passing.

## 2026-07-23 — Served release identity implementation

- Added fail-closed API revision/provenance on `/health`.
- Added a clean-HEAD-verified canonical detached-SHA frontend stamp generator.
- Added Vite HTML metadata and a revision/digest-bound complete JavaScript
  manifest.
- Focused result: 28 tests passed; Ruff check/format, TypeScript typecheck,
  production build, and diff checks passed.

## 2026-07-23 — Read-only cross-surface implementation

- Added exact protected-target policy validation and minimal CLI environments.
- Added direct API and real CLI subprocess discovery adapters with first-page
  cursor omission.
- Added typed configured-source discovery to the deployed ingestion UI.
- Added Python Playwright browser observation with service workers blocked and
  off-policy API rejection.
- Added non-overridable retired-route baseline and revision/digest-bound asset
  scanning with count, byte, MIME, redirect, and deadline guards.
- Focused result: 21 Python tests and 7 Vitest cases passed; Ruff, mypy,
  TypeScript typecheck, production build, and diff checks passed.

## 2026-07-23 — Guarded mutation and evidence implementation

- Added exact target classification, redundant production mutation rejection,
  bounded checked-in JSON fixtures, one-shot canonical ingestion, and terminal
  operation polling with stable ambiguous-submit handling.
- Added a minimized JSON evidence contract and packaged runtime copy with
  schema, semantic, provenance, time-window, byte-bound, and secret-name
  validation.
- Added safe validator-failure envelopes and standalone run/validate entry
  points that import correctly from outside the repository.
- Focused result: 41 release-smoke tests passed; Ruff, mypy, standalone
  validator, and diff checks passed.

## 2026-07-23 — CI and operator integration

- Added separate read-only production and approval-controlled staging mutation
  jobs. Callers select only the tier; protected environment variables and
  secrets supply exact target identity, origins, expected revisions, deny
  aliases, and credentials.
- Made sanitized evidence validation a prerequisite for bounded artifact
  retention and preserved a failing job outcome after safe evidence upload.
- Added a fixed-field fallback for malformed protected policy and other
  pre-observation runner failures.
- Updated local and production runbooks, including the clean detached-HEAD
  frontend stamp and served `verified_detached_sha` identity chain.
- Complete package gate: 116 Python tests and 7 Vitest cases passed; Ruff,
  mypy, TypeScript typecheck, production build, strict OpenSpec, package schema,
  dependency/DAG/lock, and diff checks passed.

## 2026-07-23 — Independent implementation and security rework

- Independent implementation and OWASP-style security reviews found fail-open
  redirect, browser credential, production identity, asset completeness,
  evidence fallback/completeness, checkout cleanliness, and package-scope
  defects.
- Disabled redirects in the real CLI's release-smoke mode and proved a custom
  admin header is never forwarded to a redirect destination.
- Moved browser login to the exact no-redirect API origin, preserved and
  verified the deployed cookie attributes, blocked every off-policy HTTP(S)
  origin and non-read-only browser method, and kept the password out of served
  JavaScript.
- Added nonempty protected production identity/origin registries for mutation,
  complete post-PWA JavaScript plus loaded-HTML retired-route scanning, and
  streaming decompressed byte/deadline enforcement.
- Hardened evidence validation against secret echo, malformed types,
  incomplete passing claims, missing mutation terminal evidence, and
  invalid/missing workflow output. The workflow now replaces rejected output
  with a separately validated safe failure envelope before retention.
- Required a detached, fully clean checkout; pinned workflow actions and uv;
  validated stamp digest/served provenance in the manual evidence contract;
  and stamped rollback uploads.
- Rework gates: 142 release/config/API tests plus 49 canonical client/CLI tests
  passed; 7 Vitest cases, TypeScript typecheck, complete post-PWA production
  build, Ruff, mypy, strict OpenSpec, package schema/dependency/DAG/lock, and
  diff checks passed.

## 2026-07-23 — Final security re-review rework

- Preserved invalid-output normalization as an explicit failed workflow outcome
  while independently validating and retaining the safe fallback envelope.
- Removed rejected failure-code values from validator diagnostics and extended
  the standalone no-echo regression.
- Routed and blocked every browser WebSocket before page creation, recorded any
  attempt as a smoke failure, and exercised the boundary in real Chromium.
- Independent security review signed off clean on `94d49a1b`; independent
  implementation review then identified and verified the test-only redaction
  assertion improvement in `c5735abf`.
- Final state: no remaining implementation, security, privacy, plan-scope, or
  validation findings.
