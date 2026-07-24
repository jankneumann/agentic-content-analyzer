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
