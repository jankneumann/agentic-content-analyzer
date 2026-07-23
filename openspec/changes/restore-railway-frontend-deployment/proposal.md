# Restore the Railway frontend deployment

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `restore-railway-frontend-deployment`
> Effort: M
> Priority: 2

## Problem

The production `aca-app` Railway service is failed and stopped. Its isolated
`/web` Railpack build detects npm, but `npm run build` invokes `pnpm`, which is
not installed. The same build script then invokes the repository's Python/uv
contract generator even though the isolated frontend build context does not
contain that toolchain or its source inputs.

The corrected frontend code already discovers `/api/v1/capabilities` and
submits `POST /api/v1/ingestions`, but it cannot replace the retired production
revision until the build and CI boundaries match their available toolchains.

## Goals

- Make the checked-in isolated Railway frontend build deterministic and
  Node-only.
- Preserve generated workflow-contract drift enforcement in CI with the full
  repository toolchain.
- Run the exact production frontend build in CI.
- Deploy and verify the capability-driven ingestion frontend in production.
- Record production evidence that canonical ingestion traffic replaced the
  retired mutation routes.

## Non-Goals

- Changing the canonical ingestion API or generated workflow models.
- Moving the Railway frontend service to a shared monorepo root.
- Adding Python or uv to the production static-site image.
- Removing legacy endpoint fixtures outside the deployed capability-driven
  ingestion surface.

## Approaches Considered

### A. Isolated npm build plus full-toolchain CI gate — selected

Keep Railway's `/web` isolated root, make the production build script
package-manager neutral, commit the npm lockfile Railpack consumes, and run
contract drift plus the same npm build in a dedicated CI job.

**Why selected:** it matches the observed production environment, keeps the
static build small, makes dependency resolution reproducible, and preserves
contract enforcement where the generator inputs and uv are available.

### B. Install pnpm, Python, and uv in the Railway build

Teach Railpack to install every tool used by the current build script.

**Rejected:** the isolated root still lacks the generator's repository inputs,
and a static frontend release should not depend on the backend's Python
toolchain.

### C. Move the frontend service root to the monorepo root

Change Railway's external service setting, build the pnpm workspace from `/`,
and point static serving at `web/dist`.

**Rejected:** this expands the build context, introduces a platform-only
configuration change, weakens the checked-in isolated-service contract, and
couples unrelated backend changes to frontend releases.

## Selected Scope

- `.gitignore`, `package.json`, `pnpm-lock.yaml`, `web/package.json`, and
  `web/package-lock.json`
- `.github/workflows/ci.yml`
- focused configuration/CI regression tests
- Railway frontend deployment evidence
- frontend deployment documentation

## Risks and Mitigations

- **Dual lockfiles drift:** CI executes the npm production build and existing
  pnpm workflows continue to enforce the workspace lock. Both package-manager
  override graphs pin the same audit-safe `protobufjs` release.
- **Vulnerable production graph:** CI runs `npm audit --omit=dev
  --audit-level=high`; high or critical production findings block promotion.
- **Tracked lock omitted from CLI upload:** the repository explicitly
  unignores `web/package-lock.json`, and a regression uses Git's ignore engine
  to ensure Railway's uploader includes it.
- **Contract drift escapes production build:** CI runs the generator check as a
  separate required step before the production build.
- **Unverified revision reaches production:** deployment is permitted only
  from a clean, pushed commit whose draft PR produced a successful
  `frontend-release` GitHub check for that exact SHA. Upload runs from a
  detached checkout at the same SHA, and Railway metadata must identify it.
- **Wrong production target:** every Railway command uses project
  `4b0db3b8-110d-4a13-81d5-440aa2ddc98d`, environment
  `cd39a506-8d8f-4aa2-b298-766fde2b8dd8`, and service
  `00281b0e-9de9-414d-844e-da3ab02836f5`.
- **Unsafe production canary:** make exactly one visible UI submission of a
  URL command for a uniquely marked `https://example.com/` URL, with preserved
  browser network capture and no repeat after an ambiguous response. Retain
  its operation/content as labeled release evidence unless a supported cleanup
  path is confirmed.
- **Incomplete release evidence:** a checked-in validator rejects blank or
  inconsistent candidate, rollback, CI, Railway build, browser, operation,
  attributed in-window log, and retired-route fields.
- **Rollback:** capture the active deployment, last successful deployment,
  public domain, exact target IDs, and rollback command before deployment.
  Abort if no recoverable prior release exists.

## Acceptance Outcomes

- A clean Railway frontend build succeeds from the checked-in service
  configuration.
- CI runs both the production frontend build and the generated
  workflow-contract drift check.
- The active production frontend revision discovers capabilities and submits
  `POST /api/v1/ingestions`.
- Production traffic no longer calls `POST /api/v1/contents/ingest` or
  `POST /api/v1/content/save-url`.

## Approval

Approved through parent roadmap `roadmap-workflow-surface-reliability` on
2026-07-23.
