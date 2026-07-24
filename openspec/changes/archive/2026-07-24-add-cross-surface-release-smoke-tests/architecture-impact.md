# Architecture Impact: add-cross-surface-release-smoke-tests

## Summary

The change adds an operational compatibility observer around the existing
frontend, CLI, and workflow API. It publishes immutable build identity at the
served frontend/backend boundary and introduces a release runner plus evidence
contract. It does not create a new service, database table, queue, or workflow
state machine.

## Affected Flows

1. **Backend build/runtime → `/health`**
   - Railway's immutable deployment metadata supplies the API revision.
   - Liveness returns the normalized non-secret revision and allowlisted
     provenance with existing health.

2. **Frontend build → served HTML**
   - A repository stamp command binds a clean detached SHA to the Railway CLI
     upload even when platform commit metadata is null.
   - Vite selects trusted revision metadata during the build.
   - The revision/provenance are embedded in the served document and a complete
     revision-bound JavaScript asset manifest.

3. **Release runner → API/CLI/browser**
   - Approval-protected target policy pins identity, exact origins, expected
     revisions, and nonempty production identity/origin registries before
     credentials can be attached.
   - Direct HTTP and a no-redirect real CLI subprocess perform canonical
     discovery.
   - The ingestion UI uses its typed frontend client for configured-source
     first-page discovery.
   - A fresh Playwright context authenticates directly to the exact API, keeps
     the password out of served JavaScript, and loads only exact protected
     frontend/API origins with read-only methods while blocking every
     WebSocket attempt.
   - Loaded HTML plus manifest-complete Rollup/PWA JavaScript and normalized
     observed requests are checked against a non-overridable retired-mutation
     baseline with streaming byte/deadline bounds.

4. **Approved staging runner → durable operation**
   - Redundant target guards authorize one canonical ingestion.
   - Existing operation GET endpoints provide terminal state.
   - No alternative execution or persistence model is introduced.

5. **Release workflow → retained evidence**
   - Schema and semantic validation precede retention of a sanitized JSON
     artifact; invalid runner output is replaced with a separately validated
     minimal failure envelope while preserving a failed normalization signal.
   - Promotion consumes observed revisions and pass/fail checks.

## Compatibility and Risk

- **API compatibility**: `/health` only gains additive strings; workflow
  OpenAPI is unchanged.
- **Frontend compatibility**: inert meta elements and an asset manifest are
  additive; configured-source discovery uses the existing canonical GET.
- **Data risk**: production default is read-only; staging mutation is one-shot
  and idempotent.
- **Security risk**: credentials remain environment-only and exact-origin
  pinned; redirects, browser writes, and WebSockets are disabled; retained
  evidence is allowlisted and contains no raw traffic.
- **Performance risk**: no request-path overhead except constant-time revision
  normalization on liveness; asset scanning runs outside services.
- **Rollback**: remove the gate/workflow and additive revision metadata. No data
  migration is needed.

## Dependency Boundaries

- Python runner: existing `httpx` and Pydantic plus the explicit
  `release-smoke` JSON Schema extra.
- Browser: Playwright/Chromium pinned through the explicit `release-smoke`
  Python extra.
- CLI: installed repository `aca` entry point, not an in-process shortcut.
- CI: commit-pinned GitHub Actions with read-only repository permission,
  protected environment secrets, reviewed ref restrictions, and no
  self-approval.
