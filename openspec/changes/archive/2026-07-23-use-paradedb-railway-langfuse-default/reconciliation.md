# Reconciliation: ParadeDB and Langfuse defaults

**Disposition**: Archive the implemented configuration/image foundation;
continue documentation and production proof in
`verify-production-paradedb-langfuse`.

## Verified foundation

- Langfuse defaults and profile variants are implemented and validated.
- Canonical image `ghcr.io/jankneumann/aca-postgres:17-railway` is public; the
  observed amd64 digest is
  `sha256:ce9d3233b69fd559fc88f45a44bc8f2bd3d1a174e9524390b0855331dc01296d`.
- RI-03 passed 86 profile/MCP tests and validated nine profiles.

## Outstanding proof

Documentation still includes the nonexistent `newsletter-postgres` identity
and stale version claims. No retained evidence proves the production Railway
database digest, required extension versions, active `paradedb_bm25` strategy,
or revision-correlated Langfuse trace delivery.

Implemented profile behavior was manually merged into the main spec. The
historical delta's unsupported unreachable-endpoint warning and production
claims SHALL NOT sync automatically.
