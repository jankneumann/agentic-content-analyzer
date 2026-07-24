# Design: Production ParadeDB/Langfuse proof

## Preflight

- Resolve exact Railway project, environment, database service, application
  service, current image/digest, public domain, and last known-good rollback.
- Back up and validate restore steps before database mutation.
- Prove the target GHCR manifest and expected architecture, bind its digest to
  a reviewed repository commit through the trusted workflow or attestation,
  retain SBOM and vulnerability-scan evidence, and deploy by digest.
- Define abort thresholds for health, migrations, search, and trace delivery.

## Acceptance evidence

1. Railway database service records the expected immutable image digest.
2. SQL returns installed versions for `vector`, `pg_search`, `pgmq`, and
   `pg_cron`.
3. Authenticated BM25 search reports `meta.bm25_strategy=paradedb_bm25`.
4. A uniquely labeled, non-sensitive generation produces a Langfuse trace
   correlated to the application revision and bounded verification window.
5. Health/readiness remain green and rollback remains executable.

Evidence must omit credentials, connection strings, raw headers, and user
content.
