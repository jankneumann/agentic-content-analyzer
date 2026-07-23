# Tasks: Restore the Railway frontend deployment

> Change ID: `restore-railway-frontend-deployment`
> Selected approach: isolated npm build plus full-toolchain CI gate

## Phase 1 — Production build boundary (`wp-production-build`)

- [x] 1.1 Write failing regressions for the isolated Railway build contract. **(S)**
  **Spec scenarios:** Reproducible isolated frontend build / Clean Railway build;
  Production build stays toolchain-local
  **Design decisions:** D1, D2
  **Dependencies:** None
- [x] 1.2 Make the production build package-manager neutral. **(S)**
  **Dependencies:** 1.1
- [x] 1.3 Commit and verify the exact frontend npm dependency graph. **(M)**
  **Dependencies:** 1.1
- [x] 1.4 Ensure Railway's Git-ignore-aware uploader includes the tracked
  frontend npm lockfile. **(S)**
  **Dependencies:** 1.3
- [x] Checkpoint: assert Node 22 package/runtime parity, run configuration
  tests, `npm ci`, and `npm run build`; review lockfile scope.

## Phase 2 — CI release parity (`wp-ci-parity`)

- [x] 2.1 Write a failing regression for the required frontend CI steps. **(S)**
  **Spec scenarios:** CI frontend release parity / Generated contracts drift;
  Production frontend does not compile; Both release boundaries pass
  **Design decisions:** D3
  **Dependencies:** 1.2, 1.3
- [x] 2.2 Add the full-toolchain frontend release job to CI. **(M)**
  **Dependencies:** 2.1
- [x] 2.3 Run the contract drift check, production dependency audit,
  workflow-client tests, and exact npm build locally. **(M)**
  **Dependencies:** 2.2
- [x] Checkpoint: validate workflow YAML, inspect job permissions, run
  `npm test -- --run src/lib/api/__tests__/workflow-contracts.test.ts`, and
  review the CI diff.

## Phase 3 — Deployment and evidence (`wp-production-proof`)

- [x] 3.1 Update the Railway frontend deployment runbook. **(S)**
  **Spec scenarios:** Reproducible isolated frontend build / Clean Railway build
  **Design decisions:** D1, D2, D4
  **Dependencies:** 1.2, 1.3, 2.2
- [x] 3.2 Write tests and a validator for the production evidence contract. **(M)**
  Reject blank critical fields, revision mismatch, unsuccessful CI/Railway or
  operation status, invalid/missing window bounds, missing browser/backend
  correlation, retries, and nonzero retired-route counts.
  **Design decisions:** D6
  **Dependencies:** 3.1
- [ ] 3.3 Populate the pre-deployment release manifest and rollback record. **(M)**
  Capture the active deployment, last successful deployment and revision,
  public domain, exact project/environment/service IDs, rollback command, and
  abort criteria before any production mutation.
  **Design decisions:** D4, D6
  **Dependencies:** 3.2
- [ ] 3.4 Commit and push a clean candidate, create or update its draft PR to
  `main`, then require a successful GitHub `frontend-release` check for that
  exact SHA. Record the check URL, conclusion, and checked SHA. **(M)**
  **Design decisions:** D3, D4
  **Dependencies:** 2.3, 3.3
- [ ] 3.5 Deploy the validated exact SHA from a clean detached worktree. **(M)**
  Confirm detached `HEAD` equals the checked SHA and the worktree is clean,
  then run `railway up --ci` from that repository root with explicit project,
  environment, service, and a release message containing the SHA. Query
  deployment metadata and require `meta.cliMessage` to equal
  `frontend-release <checked-SHA>` plus the active revision record to name the
  checked SHA. (`meta.commitHash` is null for CLI uploads.)
  **Spec scenarios:** Canonical production ingestion frontend / Production ingestion surface loads
  **Design decisions:** D4
  **Dependencies:** 3.4
- [ ] 3.6 Verify capability discovery and submit exactly one production canary. **(M)**
  Use `{"kind":"url","url":"https://example.com/?aca-release-smoke=<short-sha>","title":"ACA release smoke <short-sha>","notes":"restore-railway-frontend-deployment","routing_mode":"webpage","force_reprocess":false}`
  through the deployed form. Preserve browser network logging, fill the form
  once, click submit exactly once, and do not reload, double-click, script, or
  repeat an ambiguous request. Record the operation ID and terminal status.
  Retain the labeled result unless a supported cleanup path is confirmed.
  **Spec scenarios:** Production ingestion surface loads; Production ingestion is submitted
  **Design decisions:** D5, D6
  **Dependencies:** 3.5
- [ ] 3.7 Correlate browser network evidence with bounded backend logs and
  query both retired mutation paths. **(M)**
  Record public URL, UTC window bounds, capability status, canonical
  method/path/status, browser/request attribution, operation ID/status,
  backend-log correlation, retired-route counts, deployed revision, and
  rollback deployment ID in the sanitized evidence template.
  **Spec scenarios:** Canonical production ingestion frontend / Retired mutation routes remain unused
  **Design decisions:** D5, D6
  **Dependencies:** 3.6
- [ ] Checkpoint: confirm Railway `SUCCESS`, public route health, and run the
  production-evidence validator successfully.

## Phase 4 — Integration (`wp-integration`)

- [ ] 4.1 Run the complete frontend release gate from a clean dependency state. **(M)**
  Include `npm test -- --run src/lib/api/__tests__/workflow-contracts.test.ts`.
  **Dependencies:** 1.3, 2.3, 3.7
- [ ] 4.2 Populate requirement evidence and verify the pre-recorded rollback data. **(S)**
  **Dependencies:** 4.1

## Gate 2 Approval

Approved through parent roadmap `roadmap-workflow-surface-reliability` on
2026-07-23. The item acceptance outcomes require a successful production
frontend deployment and canonical ingestion traffic.
