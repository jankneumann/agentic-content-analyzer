# Architecture Impact: restore-railway-frontend-deployment

## Summary

The change restores the existing Railway frontend release boundary. It does not
add a service, endpoint, database migration, event, feature flag, or public API
contract. The runtime application flow is unchanged; only dependency locking,
release CI, deployment procedure, and production evidence are strengthened.

## Affected Flows

1. **Repository checkout → frontend release CI**
   - CI installs Node 22 and the Python/uv toolchain.
   - Generated workflow contracts must be current before the focused workflow
     client tests and exact production build can pass.

2. **Clean frontend upload → Railway Railpack**
   - The Git-ignore-aware uploader includes the committed npm lock through the
     explicit `.gitignore` exception.
   - Railpack detects Node 22, runs `npm ci`, and executes the manager-neutral
     `npm run build` without repository-level Python tooling.

3. **Deployed ingestion form → canonical workflow API**
   - The existing form discovers `/api/v1/capabilities`.
   - A visible URL submission uses `POST /api/v1/ingestions` and follows the
     returned durable operation to completion.
   - The retired mutation paths remain unused.

4. **Release operator → rollback and audit evidence**
   - An exact-SHA GitHub release check gates the detached Railway upload.
   - The prior known-good revision and rollback command are recorded before the
     production mutation.
   - Sanitized browser, operation, deployment, and bounded-log facts are
     validated as a durable evidence artifact.

## Compatibility and Risk

- **API compatibility**: unchanged; the canonical workflow contract is verified,
  not revised.
- **Frontend compatibility**: unchanged at runtime; the build now requires the
  declared Node 22 major and committed npm dependency graph.
- **Data risk**: one uniquely labeled URL canary was retained as release evidence;
  no persistence schema changed.
- **Security risk**: no new trust boundary or credential path. The npm and pnpm
  graphs converge on `protobufjs` 8.7.1, and CI rejects high or critical
  production audit findings.
- **Performance risk**: no runtime behavior change. Existing bundle-size warnings
  remain visible but do not block this deployment repair.
- **Rollback**: upload the pre-recorded known-good revision from a clean detached
  worktree using the sanitized command in `evidence/production-deployment.md`.

## Validation Limitation

The in-app browser runtime failed to initialize before navigation with
`Cannot redefine property: process`. The same production scenario was therefore
executed with the repository Playwright installation, and browser network facts
were correlated to authenticated read-only operation state and bounded Railway
backend logs. No canary retry was performed.
