# Architecture Impact: add-cross-surface-release-smoke-tests

## Summary

The change adds an operational compatibility observer around the existing
frontend, CLI, and workflow API. It publishes immutable build identity at the
served frontend/backend boundary and introduces a release runner plus evidence
contract. It does not create a new service, database table, queue, or workflow
state machine.

## Affected Flows

1. **Backend build/runtime → `/health`**
   - Trusted build/deployment environment supplies a revision.
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
     revisions, and production aliases before credentials can be attached.
   - Direct HTTP and real CLI subprocesses perform canonical discovery.
   - The ingestion UI uses its typed frontend client for configured-source
     first-page discovery.
   - A fresh Playwright context loads the deployed ingestion surface and records
     only allowlisted compatibility facts.
   - Manifest-complete first-party assets and normalized observed requests are
     checked against a non-overridable retired-mutation baseline.

4. **Approved staging runner → durable operation**
   - Redundant target guards authorize one canonical ingestion.
   - Existing operation GET endpoints provide terminal state.
   - No alternative execution or persistence model is introduced.

5. **Release workflow → retained evidence**
   - Schema and semantic validation precede retention of a sanitized JSON
     artifact; invalid runner output is replaced with a separately validated
     minimal failure envelope.
   - Promotion consumes observed revisions and pass/fail checks.

## Compatibility and Risk

- **API compatibility**: `/health` only gains additive strings; workflow
  OpenAPI is unchanged.
- **Frontend compatibility**: inert meta elements and an asset manifest are
  additive; configured-source discovery uses the existing canonical GET.
- **Data risk**: production default is read-only; staging mutation is one-shot
  and idempotent.
- **Security risk**: credentials remain environment-only and exact-origin
  pinned; redirects are disabled; retained evidence is allowlisted and contains
  no raw traffic.
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
- CI: GitHub Actions with read-only repository permission and protected
  environment secrets.
