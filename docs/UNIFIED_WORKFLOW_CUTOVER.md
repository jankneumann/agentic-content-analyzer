# Unified content workflow cutover

Tracking issue: [#446](https://github.com/jankneumann/agentic-content-analyzer/issues/446).
Code change: PR [#445](https://github.com/jankneumann/agentic-content-analyzer/pull/445) and
follow-up contract stabilization PRs [#449](https://github.com/jankneumann/agentic-content-analyzer/pull/449)–[#454](https://github.com/jankneumann/agentic-content-analyzer/pull/454).
Archived design: `openspec/changes/archive/2026-07-17-unify-content-workflows-agentic-surfaces/design.md` D12.

## Release identifier

There is no separate GitHub Release tag for this cutover. The external contract is:

- URL prefix: `/api/v1` (unchanged)
- OpenAPI `info.version`: `2.0.0` (`openspec/contracts/content-workflows/openapi/v1.yaml`)
- Mutation success: `202 OperationHandle` with `schema_version: 2`
- Ingestion: discriminated `IngestCommand` (`kind` required)

## Maintenance window

The coordinated **code** cutover landed on `main` 2026-07-17. The production
frontend + API evidence window is 2026-07-23T20:48Z–20:54Z (Railway
`production` environment `cd39a506-8d8f-4aa2-b298-766fde2b8dd8`). No further
scheduled maintenance window is required for this migration; later `main`
deploys continue the same contract.

## Deploy / rollback order (D12)

1. Database migrations (additive provenance columns first).
2. Queue workers (accept payload schema versions 1 and 2 during the window).
3. API, then MCP, CLI package, frontend as one release.
4. Drain version-1 jobs; do not restore legacy HTTP mutations.
5. Rollback: previous application release; keep additive columns; accept v1 jobs
   only if rolling back across the original window. Do not drop columns in the
   same release as the external break.

## Production evidence (already recorded)

From
`openspec/changes/archive/2026-07-23-restore-railway-frontend-deployment/evidence/production-deployment.md`:

- Frontend public origin: `https://app.aca.rotkohl.ai`
- `GET /api/v1/capabilities` → 200 (18 source options including URL)
- Canary `POST /api/v1/ingestions` `kind=url` → 202, operation `104` completed
- `POST /api/v1/contents/ingest` count: 0
- `POST /api/v1/content/save-url` count: 0
- Rollback not required; pinned known-good remains deployment
  `0d5201c0-b08d-4758-b70b-302e7237b6b2`

Local/CI evidence from
`docs/HANDOFF_UNIFIED_CONTENT_WORKFLOWS_2026-07-17.md`: contract/fuzz green on
`main` (CI run 29620163060); Tauri matrix green; iOS stopped at TestFlight
signing ([#453](https://github.com/jankneumann/agentic-content-analyzer/issues/453)).

## Residual (not this cutover)

- Independently installed Shortcuts still on `save-url` have **no** adapter;
  operators must recreate them ([#492](https://github.com/jankneumann/agentic-content-analyzer/issues/492),
  [API consumers](API_CONSUMERS.md)).
- TestFlight/Fastlane: #453.
- Residual advisories: #447.

Queue drain of pre-cutover version-1 jobs is complete for any environment that
has been running `main` since 2026-07-23: workers have been emitting version 2
only, and legacy mutation routes are absent from the composed API.