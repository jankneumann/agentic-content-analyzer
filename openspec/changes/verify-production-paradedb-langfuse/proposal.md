# Change: Verify production ParadeDB and Langfuse

## Why

Langfuse profile defaults are implemented and the canonical ParadeDB image is
publicly pullable, but repository documentation still names a nonexistent
image and stale component versions. No durable evidence proves that production
Railway runs the published digest, exposes the required extensions, selects
`paradedb_bm25`, or delivers a revision-correlated Langfuse trace.

## Source and completed scope

- Extracted from archived `use-paradedb-railway-langfuse-default`.
- Completed and excluded: Langfuse provider implementation, profile defaults,
  profile tests, custom ParadeDB Dockerfile, image publication workflow, and
  public `aca-postgres:17-railway` manifest.
- This change requires explicit production authority before any mutation.

## What Changes

- Make `ghcr.io/jankneumann/aca-postgres:17-railway` the single documented
  image identity and derive version claims from the Dockerfile/build.
- Bind the deployed immutable digest to a reviewed commit and trusted build
  workflow or attestation, retaining sanitized SBOM and vulnerability-scan
  evidence.
- Record the active database image/digest and rollback target before cutover.
- Verify `vector`, `pg_search`, `pgmq`, and `pg_cron` versions in production.
- Verify authenticated BM25 metadata reports `paradedb_bm25`.
- Correlate application revision and one sanitized production generation trace
  with Langfuse arrival.

## Capability

- `production-paradedb-langfuse-verification`

## Impact

Documentation and deployment evidence will change. A Railway database cutover
may change external production state and therefore requires scoped approval,
backup/restore validation, abort criteria, and rollback evidence.
