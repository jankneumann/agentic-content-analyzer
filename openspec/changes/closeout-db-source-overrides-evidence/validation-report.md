# Validation Report: closeout-db-source-overrides-evidence

**Date**: 2026-09-21 23:15:00 EDT
**Commit**: `8c6af6839a6bbb35e0d402431ee56d2efea68c45`
**Validated tree**: feature worktree at `8c6af683`
**Branch**: `openspec/closeout-db-source-overrides-evidence`

## Phase Results

- ✓ Contract/API/CLI: 118 passed.
- ✓ Frontend: API/component tests passed; component 10/10; typecheck and production build passed.
- ✓ Browser: Chromium source-settings journey 7/7 passed with deterministic mocks.
- ✓ Migration: 2/2 passed with no skips against a fresh Claimable PostgreSQL 17 database.
- ✓ Contract/spec: generated drift check and strict OpenSpec validation passed.
- ✓ Documentation/archive: required operator anchors are present and the archived source change is untouched.
- ⚠ Architecture: scoped flows 0 findings; 15 advisory file-size nits; baseline diff target unavailable.
- ○ Requirement-to-contract gate: unavailable because `packages/gen-eval/scripts/check_traceability.py` is not present; the 7/7 change-context matrix was verified directly.
- ✓ Live smoke: rootless Podman dependency plus a local API returned health/ready 200 and source auth 401/200/403 for missing/valid/invalid credentials.
- ⚠ Security: ZAP had 0 failures and one low-risk cache warning; Python audit was clean; frontend audit reproduced 29 high pre-existing advisories on both main and the feature branch (issue #530).

## Spec Compliance

**Status**: pass

All 7 requirements have mapped files, tests, and passing evidence in
`change-context.md`. Both WP7 tasks are complete. `openspec validate
closeout-db-source-overrides-evidence --strict` passes.

## Smoke Tests

**Status**: pass

The API ran against PostgreSQL 17 and rootless FalkorDB. `/health` and `/ready`
returned 200; `/api/v1/sources` returned 401 without credentials, 200 with the
admin key, and 403 with an invalid key. The reusable generic bundle passed
10/11; its one failure hardcodes the unrelated coordinator endpoint/header
`POST /memory/store` with `X-API-Key`, despite the validator documenting those
values as configurable. Change-specific API lifecycle, legacy error,
no-mutation, privacy, CLI, and contract suites passed 118/118.

## Security

**Status**: pass

ZAP baseline via rootless Podman reported 0 failures and one low-risk
`Non-Storable Content` warning on authenticated root/robots responses. Local
Python `pip-audit` reported no known vulnerabilities. Frontend `pnpm audit`
reported 29 high and 6 moderate transitive advisories, but the identical count
and families reproduce on `main`; follow-up is tracked in GitHub issue #530.
Focused security evidence also passed: owner/admin authentication, 401/403
no-mutation guarantees, opaque Obsidian keys, malformed-key browser redaction,
and fail-closed audit normalization including 40-layer percent encoding.

## E2E Tests

**Status**: pass

Playwright Chromium passed 7/7 source-settings scenarios. Component tests
passed 10/10, covering Readwise add, YAML/DB origins, opaque Obsidian display,
mutation recovery, and row-level race prevention.

## Database Evidence

**Status**: pass

The disposable-database suite passed 2/2 on PostgreSQL 17, proving the
predecessor-to-head migration, table shape, JSONB/defaults/indexes, sentinel
preservation, repeat-head safety, and incompatible-table diagnostics.

Temporary database claim URL (expires 2026-09-25):
`https://neon.new/claim/01a0c718-d1ee-735e-9bab-c5f41fd458bd`

## Architecture

**Status**: warn

Architecture freshness completed; scoped flow validation returned 0 findings.
The generic linter reported 15 file-size nits on longstanding generated,
documentation, lock, and fixture files. The repository does not define the
requested `architecture-diff` Make target.

## Result

**PASS WITH WARNINGS** — All change-specific acceptance checks pass. Remaining
warnings are pre-existing frontend dependency advisories tracked in issue #530,
generic architecture file-size nits, and a reusable smoke assertion that is
hardcoded for a different service contract.
