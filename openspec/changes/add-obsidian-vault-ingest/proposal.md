# Change: Add Obsidian Vault Ingestion

## Why

Obsidian Web Clipper provides a useful cross-device capture surface, but ACA has no
durable way to ingest those captured notes. A vault adapter can reuse plain Markdown
without creating another browser or mobile client, provided it participates in the
same typed source, queue, persistence, recovery, and alerting contracts as every other
ingestion source.

The earlier bridge proposal assumed a process-local poller and paths in public source
configuration. That model predates `SOURCE_REGISTRY`, generated workflow contracts,
opaque configured-source keys, and durable ingestion outcomes. It also cannot safely
route a laptop path to an arbitrary cloud worker. This revision makes the deployment
and security boundary explicit before implementation.

## What Changes

### Canonical Source Vertical

- **NEW**: An `obsidian_vault` configured source and typed ingestion command in the
  canonical OpenAPI discriminator, generated Python and TypeScript contracts, and
  `SOURCE_REGISTRY`.
- **NEW**: Equivalent CLI, HTTP, MCP, worker, scheduler, and capability-driven frontend
  projections. CLI and MCP submissions return the standard durable
  `OperationHandle`; there is no transport-specific task or polling API.
- **NEW**: Deterministic fixtures and explicit real-ingestion policy so registry
  completeness remains enforced at test collection.

### Worker-Local, Bounded Scan

- **NEW**: One `ingestion.execute` operation performs one bounded scan of a vault that
  is mounted on the executing worker. A deployment may schedule repeated commands,
  but no adapter-owned daemon, filesystem watcher, or parallel run-state model is
  introduced.
- **NEW**: Startup and capability readiness report a source unavailable when its mount
  is absent. A personal-device vault is not remotely accessible to Railway unless the
  deployment deliberately mounts or synchronizes it onto the worker selected for the
  operation.
- **NEW**: Scan bounds cover files, bytes, recursion depth, elapsed time, note size,
  frontmatter size/complexity, and concurrency. Cancellation is checked between files.

### Private Configuration and Path Safety

- **NEW**: Each configured vault has a stable non-secret `vault_id`; its absolute
  `vault_path` remains private configuration and never becomes a command field,
  natural locator, public capability value, log field, or durable operation result.
- **NEW**: Database overrides may store the private path because source configuration
  is server-side, but every public/admin projection substitutes an opaque HMAC source
  key and safe allowlisted fields. Deployment-owned allowed roots cannot be widened by
  a database override.
- **NEW**: Reads are relative to an approved root, reject every symlink and traversal
  component, use no-follow file access with post-open identity checks, and never
  dereference Obsidian embeds or attachments.

### Strict Clip and Incremental State Contracts

- **NEW**: UTF-8 notes require bounded YAML frontmatter containing an HTTP(S)
  `source_url` and timezone-aware `captured_at`. Optional `capture_client` and
  `content_type_hint` fields have closed, documented values; missing required or
  malformed values produce typed failures.
- **NEW**: The captured Markdown is authoritative content. `source_url` supplies
  provenance and canonical identity only; the adapter does not refetch it.
- **NEW**: A private state store keyed by opaque vault identity and normalized relative
  path records file fingerprints, claims, terminal status, and the linked content.
  Transactional claims and immutable ingest-event identity make overlapping scans and
  crash reconciliation idempotent.
- **NEW**: Re-observing unchanged bytes is a no-op. Changed bytes at the same path are
  reprocessed. A rename is a new note-level event but canonical identity can link it to
  existing primary content without deleting the old state or content.

### Read-Only Markdown Normalization

- **NEW**: Frontmatter is removed from the stored body; wikilinks, callouts, and embeds
  receive deterministic readable fallbacks. Raw HTML and URI text remain inert data
  and continue through existing renderer sanitization.
- **NEW**: Multiple clips of the same canonical URL preserve note-level Markdown and
  annotations as distinct Obsidian content records linked to one canonical primary.
- **NEW**: ACA never writes `ingest_status`, tags, or generated content into the vault,
  and never moves files in v1.

## Scope and Non-Goals

Version 1 does not include:

- a laptop-to-cloud companion bridge or remote filesystem transport;
- a long-lived poller or filesystem watcher owned by the adapter;
- attachment or embedded-file dereferencing;
- moving, deleting, tagging, or otherwise writing vault files;
- missing-`captured_at` fallback to filesystem metadata;
- knowledge-base export, bidirectional sync, or changes to
  `src/sync/obsidian_exporter.py` ownership;
- a new operation type, manual path-based replay API, or a second status machine.

## Impact

- **New capability**: `obsidian-vault-ingest`
- **Modified capability**: `source-capability-registry`
- **Modified capability**: `real-ingestion-ci`
- **Likely implementation areas**:
  - OpenAPI and generated workflow contracts
  - typed source configuration and safe override projection
  - source registry, MCP manifest, worker dispatch, and capability UI tests
  - path-safe scanner, strict parser/normalizer, state migration/repository
  - canonical content persistence, fixture matrix, live-adapter policy, and docs
- **Operational dependency**: a worker-local, deployment-approved filesystem mount;
  no mandatory external service or sync provider is added.

## Acceptance Boundary

The change is complete only when an Obsidian command can be submitted through CLI,
HTTP, MCP, and the frontend, reaches a terminal standard `OperationHandle`, persists
an operation-native typed outcome, and passes registry parity, fixture, real-ingestion,
migration, path-security, concurrency, cancellation, retry, idempotency, and redaction
tests. Vault ingress must remain demonstrably independent of knowledge-base export and
sync modules.
