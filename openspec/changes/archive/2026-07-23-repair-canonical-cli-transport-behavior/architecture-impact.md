# Architecture Impact: repair-canonical-cli-transport-behavior

## Summary

The change is bounded to existing CLI, shared HTTP-client, test, dependency-lock, and
local-profile seams. It does not add a service, endpoint, database migration, event,
feature flag, or public contract revision.

## Affected Flows

1. **Discovery command → shared workflow client → canonical API**
   - Optional cursor parameters are constructed once in `WorkflowApiClient`.
   - An absent cursor is omitted from the request; present opaque cursors are preserved.
   - Server-side cursor validation remains strict and unchanged.

2. **CLI command → machine-readable output**
   - Discovery and graph commands keep stdout to one JSON document in JSON mode.
   - Graph failures use a structured `{error, success}` payload while a readable
     diagnostic is emitted to stderr.
   - Human-mode rendering remains on the existing Rich console path.

3. **CLI tests → external/async boundaries**
   - Curation tests select RSS explicitly instead of consulting ambient credentials.
   - Graph tests exercise the real coroutine consumer with async mocks and close the
     graph client deterministically.

4. **Locked environment → CLI startup**
   - The optional Crawl4AI dependency set constrains `chardet` to the Requests-compatible
     major version.
   - The tracked local profile uses canonical Neo4j setting names.

## Compatibility and Risk

- **API compatibility**: unchanged; malformed empty cursors are prevented at the caller
  boundary rather than accepted by the API.
- **CLI compatibility**: documented command-local `--json` support is restored.
  Failure output in JSON mode becomes parseable and intentionally differs from legacy
  human text.
- **Data risk**: none; no storage or migration changes.
- **Security risk**: none identified; no credential, authorization, or trust-boundary
  change.
- **Performance risk**: negligible; request parameter filtering is constant-size and
  output handling remains linear in response size.
- **Rollback**: revert the focused client/output/configuration commits; no data rollback
  is required.

## Validation Limitation

The generated architecture-flow artifact is absent from this checkout, so automated
graph validation could not run. Manual dependency-direction review found no new layer
edge or boundary violation. The dependent `ri-04` roadmap item owns deployed
cross-surface smoke evidence.
