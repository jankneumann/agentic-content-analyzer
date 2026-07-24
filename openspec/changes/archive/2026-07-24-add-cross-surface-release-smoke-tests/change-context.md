# Change Context: add-cross-surface-release-smoke-tests

## Requirement Traceability Matrix

| Req ID | Description | Contract Ref | Decision | Planned files | Planned tests |
|---|---|---|---|---|---|
| cross-surface-release-smoke.1 | Observe immutable deployed revisions | `contracts/README.md` | D1 | `src/api/health_routes.py`, `web/vite.config.ts`, detached-SHA stamp script, release runbook | health provenance, stamp safety, CLI-upload, and Vite artifact tests |
| cross-surface-release-smoke.2 | Read-only API/CLI/frontend smoke | workflow OpenAPI v1 | D2, D3 | `pyproject.toml`, `uv.lock`, `src/release_smoke/**`, frontend workflow client/UI, runner script | API, subprocess, client, Playwright fixture |
| cross-surface-release-smoke.3 | Pin credential-bearing targets | protected target policy | D2, D4, D6 | target policy and runner guards | origin, redirect, alias, browser-destination tests |
| cross-surface-release-smoke.4 | Reject retired mutations completely | `contracts/retired-workflow-mutations.json` | D3 | Vite asset manifest and runner scanner | lazy asset, limit, digest, redirect, route-normalization tests |
| cross-surface-release-smoke.5 | Guard staging mutation and fixture | workflow OpenAPI v1 | D4 | mutation runner and checked-in fixture | target identity, path safety, one-shot, terminal polling |
| cross-surface-release-smoke.6 | Sanitize evidence | `contracts/release-smoke-evidence.schema.json` | D5 | report model and validator | conditional null, schema, secret, URL, payload, failure envelope |
| cross-surface-release-smoke.7 | Validate before retaining promotion evidence | workflow configuration | D6 | `.github/workflows/release-smoke.yml`, docs | workflow policy/order configuration tests |

## Design Decision Trace

| Decision | Rationale | Implementation boundary |
|---|---|---|
| D1 | Deployment labels alone do not prove served identity. | `/health` and frontend HTML |
| D2 | A real subprocess and browser catch integration drift hidden by in-process tests. | runner adapters |
| D3 | Stale dormant chunks must fail before execution. | browser observation and asset scanner |
| D4 | Production mutation must be structurally impossible by default. | target policy and separate mutation path |
| D5 | Release proof must be durable without becoming a data-exfiltration artifact. | strict report schema and validator |
| D6 | Promotion reads production; only protected non-production jobs mutate. | GitHub workflow job boundary |

## Review Findings

| Finding | Severity | Disposition | Resolution |
|---|---|---|---|
| R04-PLN-001 | blocker | fixed | Protected exact target identity/origins, HTTPS, redirect rejection, production aliases, and observed API destination are mandatory before credentials. |
| R04-PLN-002 | blocker | fixed | Added typed frontend configured-source discovery, actual ingestion-surface invocation, tests, locks, and scopes. |
| R04-PLN-003 | blocker | fixed | Evidence validation precedes upload; malformed runner output is discarded for a separately validated minimal failure envelope. |
| R04-PLN-004 | should-fix | fixed | Schema permits null observations only for failed runs; semantic rules require corresponding codes and complete pass observations. |
| R04-PLN-005 | should-fix | fixed | Promotion uses full commit SHAs with allowlisted provenance and forbids runtime relabeling. |
| R04-PLN-006 | should-fix | fixed | Added a non-overridable baseline for both retired production mutations; runtime may only add routes. |
| R04-PLN-007 | should-fix | fixed | Vite emits a revision/digest-bound complete asset manifest with explicit count, byte, redirect, MIME, and deadline limits. |
| R04-PLN-008 | should-fix | fixed | Dedicated `release-smoke` Python extra pins Playwright/JSON Schema and CI installs Chromium explicitly. |
| R04-PLN-009 | should-fix | fixed | Mutation uses only bounded, schema-validated JSON fixtures beneath a checked-in root; shell execution is prohibited. |
| R04-PLN-010 | should-fix | fixed | Idempotency is deterministically derived as `aca-release-smoke-v1:<run_id>`. |
| R04-PLN-011 | should-fix | fixed | The package that changes frontend discovery now runs its focused Vitest, typecheck, and production build before integration. |

## Coverage Summary

- Requirements traced: 7/7
- Planned automated coverage: 7/7
- External deployment required for deterministic tests: no
- Production/staging evidence required for change archive: workflow/configuration
  proof and local deployed-fixture proof; live credentials are not assumed
