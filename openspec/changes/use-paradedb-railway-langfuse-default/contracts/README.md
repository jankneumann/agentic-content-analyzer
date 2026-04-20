# Contracts: use-paradedb-railway-langfuse-default

## Applicability Assessment

This change is **configuration-only** — no new API endpoints, database schemas, or event payloads are introduced or modified.

### Evaluated Contract Sub-Types

| Sub-Type | Applicable? | Reason |
|----------|-------------|--------|
| OpenAPI | No | No API endpoint changes — all changes are to YAML profile files and documentation |
| Database | No | No schema changes — ParadeDB extensions are already supported; no migrations needed |
| Event | No | No new events — observability provider change is transparent to event system |
| Type generation | No | No new types — existing `ObservabilityProviderType` literal already includes `"langfuse"` |

### Why No Contracts

Both changes operate at the **configuration layer**:

1. **Langfuse default**: Changes YAML profile values (`providers.observability`) and adds credential references. The Langfuse provider code (`src/telemetry/providers/langfuse.py`) and factory (`src/telemetry/providers/factory.py`) already handle the `"langfuse"` case — no interface changes.

2. **ParadeDB on Railway**: Publishes an existing Dockerfile as a GHCR image and documents the deployment path. The Railway database provider (`src/storage/providers/railway.py`) already supports ParadeDB extensions — no code changes needed.

The existing provider Protocol interfaces (`ObservabilityProvider`, `DatabaseProvider`) are unchanged.
