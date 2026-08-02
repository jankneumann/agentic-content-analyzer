# Technical Design: Obsidian Vault Ingestion

## Context

ACA now has a canonical source registry, generated command contracts, durable
`ingestion.execute` operations, opaque configured-source keys, operation-native
outcomes, reconciliation, terminal telemetry, and exact fixture completeness checks.
Obsidian vault ingress must extend those systems rather than add a local poller or a
parallel status API.

The filesystem is a special trust and deployment boundary. A path valid on a laptop is
not valid on an arbitrary Railway worker. Version 1 therefore supports only vaults
mounted on the worker that executes the command. Deployments with distributed workers
must route the source to a compatible worker pool; capability readiness fails closed
when that guarantee is absent.

## Goals

1. Add one complete canonical ingestion source across every supported surface.
2. Preserve clipped Markdown as authoritative content without refetching the URL.
3. Make each scan bounded, cancellable, durable, idempotent, and crash-recoverable.
4. Keep absolute paths, note names, URL details, and exception text out of public
   contracts and telemetry.
5. Keep vault ingress read-only and separate from Obsidian knowledge-base export.

## Non-Goals

- remote laptop-to-cloud file transfer;
- adapter-owned polling daemons or filesystem watchers;
- attachments, embedded file reads, file moves, or frontmatter writeback;
- importing from or changing `src/sync/obsidian_exporter.py`;
- accepting arbitrary Obsidian template variants.

## Architecture

```text
CLI / HTTP / MCP / capability UI / durable scheduler
                         |
                         v
          ObsidianVaultIngestCommand
       (opaque source_key + public scan options)
                         |
                         v
             OperationService / pgqueuer
                         |
                         v
      worker-local configured-source snapshot
                         |
                         v
 bounded path-safe scan -> strict parse -> normalize
                         |
                         v
 claim/event state -> Content persistence/linking
                         |
                         v
 typed IngestionResponse -> OperationHandle + RI-09 telemetry
```

## Decisions

### D1. Use one bounded durable scan command

`ObsidianVaultIngestCommand` is a member of the canonical `IngestCommand` union and is
dispatched by `IngestionService.execute()`. It accepts the configured source key plus
safe options such as `max_items` and `force_reprocess`; it never accepts a path or note
name. API submission attaches the authoritative configured-source snapshot just like
other repeatable sources, and callers cannot supply that snapshot.

One command scans at most one configured vault and returns one canonical
`IngestionResponse`. Existing scheduling support may periodically submit the command
using a bounded idempotency bucket. Overlapping scans are safe through per-note claims;
there is no infinite worker job, watcher, per-note child operation, or new operation
type. Queue cancellation is checked before enumeration, between candidates, and before
persistence. Manual replay uses the existing retry or the same command with
`force_reprocess`; paths never become replay parameters.

### D2. Make worker-local topology explicit

A source is ready only when all of these are true:

- its private path resolves beneath a deployment-owned allowed root;
- the root and ingest directory are mounted, readable, and locally accessible to the
  selected worker pool;
- the deployment guarantees commands for that source execute on a compatible pool.

Local single-worker deployments satisfy this naturally. Railway support requires an
explicit persistent/synchronized mount and compatible worker routing; a user's device
path is not supported remotely. The first implementation may fail closed outside a
single compatible worker topology. A companion snapshot bridge is a separate future
change because it would introduce a new transport and credential boundary.

### D3. Use repeatable private source configuration

The source discriminator is `obsidian_vault`. Each `ObsidianVaultSource` contains:

- `vault_id`: required stable non-secret identifier and natural locator;
- `name`: optional operator label;
- `vault_path`: private absolute server path;
- `ingest_folder`: private relative path beneath the vault;
- bounded defaults for maximum files, bytes, recursion depth, duration, note size,
  frontmatter size/complexity, settle interval, and concurrency;
- `enabled` and existing schedule fields where supported.

The natural key is derived from `vault_id`, never `vault_path`. Public configured-source
identity uses the existing HMAC `src_...` key. Database source overrides may contain
the private path for server-side operation, but capability discovery, source-management
responses, operation inputs/results, errors, events, and logs expose only opaque keys
and safe allowlisted fields. Deployment-owned `OBSIDIAN_ALLOWED_ROOTS` is host policy,
not source override data; overrides can narrow it but cannot extend it. Empty allowed
roots disable the source.

### D4. Land the source vertical atomically

Registry completeness checks run during test collection, so registration is one green
synchronization package containing:

- OpenAPI command discriminator and generated Python/TypeScript bindings;
- runtime model re-exports and `ObsidianVaultSource` configuration union;
- `SOURCE_REGISTRY` descriptor, orchestrator dispatch, scheduling/capability metadata,
  and emitted `ContentSource.OBSIDIAN` declaration;
- hand-written MCP function, source-to-tool map, and exact toolset manifest;
- CLI/HTTP/frontend projections and behavior tests;
- deterministic `SOURCE_FIXTURES` entry and `LIVE_ADAPTER_POLICIES` entry.

Pure parser, scanner, state, and unregistered adapter foundations land first. No commit
may leave key sets or generated contracts inconsistent.

### D5. Treat note bytes as authoritative

The parser accepts only UTF-8 Markdown with bounded YAML frontmatter. The strict clip
model requires:

- `source_url`: absolute HTTP(S), bounded length, no userinfo; queries may be used for
  canonicalization but are redacted from diagnostics;
- `captured_at`: timezone-aware RFC 3339 timestamp, with no mtime fallback;
- `capture_client`: optional bounded string defaulting to
  `obsidian-web-clipper` from an allowlist;
- `content_type_hint`: optional enum `article|thread|video|paper|other`.

YAML uses safe loading, must be a mapping, rejects custom tags, aliases beyond the
configured bound, excessive nodes/depth, unsupported types, and oversized strings.
Unknown frontmatter fields are ignored rather than persisted. The normalized body is
the clipped payload; the adapter never refetches `source_url`, avoiding both content
loss and a new SSRF path.

Frontmatter is removed. Wikilinks become readable labels, callouts become blockquotes,
and `![[...]]` embeds become inert readable placeholders without opening the target.
Unsupported syntax remains text. Raw HTML and dangerous-looking URI text are never
executed and continue through existing renderer sanitization.

### D6. Use race-safe, bounded filesystem access

Enumeration is relative to an already-open trusted root and deterministic by normalized
relative path. The scanner rejects absolute paths, NULs, `..`, every symlink component,
non-regular files, ACA-generated export folders/notes, and known temporary names.
It opens with no-follow semantics, captures descriptor identity with `fstat`, reads at
most the configured bytes, then re-stats the descriptor and path. A changed inode,
size, or timestamp defers the file; content hash is computed from those exact bytes.
No validation-then-open path is trusted.

Defaults and hard ceilings are defined in source settings and tested for:

- files and total bytes per scan;
- recursion depth and elapsed duration;
- note and frontmatter bytes, YAML nodes/depth/aliases, and normalized body characters;
- settle interval and concurrent file processing.

Limit breaches produce bounded typed diagnostic codes and do not abort other safe
candidates unless the global scan bound is reached. Filesystem, clock, and sleeper
dependencies are injectable so stability and race tests are deterministic.

### D7. Persist private state with transactional claims

`obsidian_ingest_state` is private operational state, not a second user-visible run
model. Its conceptual fields are:

```text
id                         bigint primary key
configured_source_digest   fixed digest
relative_path_digest       fixed digest
file_hash                  fixed digest
observed_mtime_ns          bigint
observed_size              bigint
status                     discovered|claimed|ingested|failed|deferred
claim_token                random bounded token, nullable
lease_expires_at            timestamptz, nullable
operation_id               bigint FK pgqueuer_jobs, nullable
content_id                 bigint FK content, nullable
error_code                 bounded enum, nullable
attempt_count              bounded integer
first_seen_at/updated_at    timestamptz
```

The unique state key is `(configured_source_digest, relative_path_digest)`. An immutable
ingest-event table or equivalent unique constraint owns
`(configured_source_digest, relative_path_digest, file_hash)` so two workers cannot
persist the same version twice. Absolute and relative plaintext paths, canonical URLs,
frontmatter, exception messages, and note bodies are not stored in state.

A transaction claims an eligible fingerprint with compare-and-set/lease semantics
before content persistence. Success records `content_id` and completes the event in the
same database transaction where feasible. If the worker crashes after content commit,
reconciliation uses the immutable event/content identity to complete state without a
duplicate. Expired claims can be reclaimed within a bounded retry budget. State rows
for missing files become non-destructive tombstones only after a grace period; content
is never deleted because a synced note temporarily disappears.

### D8. Preserve note context while sharing canonical identity

`ContentSource.OBSIDIAN` identifies every stored note. Its stable source identity is
derived from the opaque configured-source identity, relative-path digest, and file hash;
raw paths are not included. Canonicalized `source_url` supplies provenance and a hashed
canonical identity.

The first note for a canonical URL may be the canonical primary. Later notes are stored
as distinct Obsidian content rows linked through the existing `canonical_id` mechanism,
so body annotations remain available without duplicating the primary identity. An
unchanged path/hash is skipped; changed bytes at the same path create or update the
note event according to existing content immutability rules. A rename intentionally
creates a new note event and may link to the same canonical primary. Invalid or missing
URLs fail; file hash is not a fallback for the required URL contract.

### D9. Use operation-native outcomes and existing telemetry

The scan returns exact persisted/skipped/failed counts, content IDs under existing
bounds, the opaque source outcome, and stable diagnostic codes. Lifecycle remains on
`pgqueuer_jobs`; note state is implementation evidence only. Expected parse, path,
limit, unavailable-mount, and claim failures map to typed ingestion diagnostics and
RFC 7807/MCP protocol errors where applicable.

Logs and results may contain operation ID, opaque source key, state/event ID, counts,
URL origin or host where allowed, and stable error code. They must not contain vault
paths, relative note names, full URLs/query strings, bodies, frontmatter, credentials,
or raw exception messages. RI-09 terminal telemetry and alert delivery cover failed or
partial scan outcomes; no Obsidian-specific alert subsystem is added.

### D10. Keep ownership boundaries explicit

Ingress implementation lives under ingestion/config/persistence ownership and does not
import the Obsidian exporter. Export/sync modules do not import the ingress adapter.
Generated ACA notes marked with the exporter generator metadata and configured managed
export directories are ignored by the scanner to prevent loops. Tests enforce the
dependency boundary.

## Rollout

1. Ship schema and unregistered foundations with feature-disabled defaults.
2. Land the atomic registry/source vertical with deterministic fixture coverage.
3. Enable one local/co-located test vault, verify bounded durable outcomes and
   redaction, then document compatible deployment topology.
4. Keep the source disabled by default until allowed roots and a compatible worker
   mount are configured.

Rollback disables the source, drains active `ingestion.execute` operations, and leaves
content/state rows intact for audit. Migration downgrade is tested separately and only
applied when no retained state is required.

## Deferred Follow-Ups

The following require separate proposals: a device-to-cloud snapshot bridge, watcher
triggers, attachment ingestion, opt-in write/move behavior, rename coalescing, and
custom template profiles.
