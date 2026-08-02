# Implementation Tasks

## Execution Policy

- Every implementation task starts with a failing test for the named scenario and ends
  with that scoped test green.
- Packages P1, P2, and P3 may proceed independently after this plan is approved. P4
  joins them. P5 exclusively owns registry/shared-contract hot files and lands as one
  atomic green commit because collection-time completeness rejects partial source
  registration.
- Generated files are regenerated from OpenAPI; they are never hand-edited.
- Vault paths, note names, full URLs, frontmatter, bodies, and raw exceptions must not
  appear in snapshots, operation evidence, logs, or test failure fixtures.
- Version 1 excludes watchers, file moves/writeback, attachments, and a remote bridge.

## P0 — Plan and Contract Decisions

- [x] 0.1 Replace the process-local poller design with one bounded durable scan and
  document the worker-local deployment boundary.
- [x] 0.2 Close v1 decisions: strict timezone-aware `captured_at`, required HTTP(S)
  `source_url`, all symlinks rejected, read-only vault access, rename as a new note
  event, and no watcher/move/attachment support.
- [x] 0.3 Define opaque configured-source identity, private database override handling,
  immutable file-version events, leased claims, canonical note linking, scan bounds,
  and redacted operation-native diagnostics.
- [x] 0.4 Validate strict OpenSpec, requirement/task traceability, and dependency graph;
  record plan-review evidence before implementation.

## P1 — Strict Clip Parser and Normalizer

Depends on: P0. Shared hot files: none.

- [x] 1.1 Add failing parser tests for valid required/optional frontmatter, defaults,
  frontmatter stripping, timezone enforcement, HTTP(S)-only URLs, userinfo rejection,
  invalid UTF-8, and unknown-field handling.
  Scenarios: `Required metadata is valid`, `Optional metadata is absent`, `Required
  metadata is missing or invalid`.
- [x] 1.2 Implement the strict clip metadata model and parser until 1.1 passes, with no
  filesystem or persistence dependency.
- [x] 1.3 Add failing adversarial YAML tests for byte/node/depth/alias/string ceilings,
  custom tags, non-mapping roots, and unsupported values, then implement bounded safe
  loading.
  Scenario: `YAML exceeds the safe contract`.
- [x] 1.4 Add failing golden normalization tests for wikilinks, aliases, headings,
  callouts, embeds, unsupported syntax, raw HTML, macros, and dangerous URI text; then
  implement deterministic inert normalization without dereferencing files.
  Scenarios: `Wikilinks and callouts are normalized`, `An embed references another
  vault file`, `Active-looking content remains inert`.
- [x] 1.5 Add canonical URL tests for host/default-port normalization, tracking removal,
  bounded length, sensitive query redaction, and deterministic hashing; then implement
  the pure canonicalizer.
  Scenario: `A URL contains tracking or sensitive query data`.

## P2 — Private State, Events, and Claims

Depends on: P0. Owns migration/model/repository files only.

- [x] 2.1 Add migration upgrade/downgrade tests for private Obsidian state and immutable
  ingest-event tables, composite digest uniqueness, content/operation foreign keys,
  bounded status/error fields, claim indexes, and absence of plaintext path/URL/body
  columns; then add the migration.
- [x] 2.2 Add repository tests proving unchanged event lookup, changed hash eligibility,
  source/path isolation, and non-destructive missing-file tombstones; then implement
  state/event persistence.
  Scenarios: `An unchanged file is observed again`, `A changed, renamed, or missing
  note is observed`.
- [x] 2.3 Add two-session PostgreSQL tests for transactional claim acquisition, losing
  contenders, lease expiry, bounded attempt count, and compare-and-set completion;
  then implement claim APIs.
  Scenario: `Two workers claim the same file version`.
- [x] 2.4 Add crash-point tests for before/after claim, content persistence, and state
  completion; then implement event/content reconciliation without duplicate inserts.
  Scenario: `A worker crashes around persistence`.
- [x] 2.5 Add persistence redaction tests showing state and repository errors retain only
  digests, opaque IDs, and stable bounded error codes.
  Scenario: `A malformed note fails`.

## P3 — Path-Safe Bounded Scanner

Depends on: P0. Owns new scanner modules/tests only.

- [x] 3.1 Add failing configuration-policy tests for deployment-owned allowed roots,
  empty-root disablement, override narrowing, worker-local mount readiness, and absence
  of path values from readiness errors; then implement the trusted root policy.
  Scenario: `The worker cannot access the configured mount`.
- [x] 3.2 Add failing containment tests for absolute paths, NUL/traversal, leaf and
  nested symlinks, non-regular files, root replacement, and swap-after-enumeration;
  then implement descriptor-relative no-follow enumeration/open/revalidation.
  Scenario: `A path or symlink escapes containment`.
- [x] 3.3 Add deterministic fake-filesystem/clock tests for temporary names, same-size
  modifications, partial writes, inode changes, settle checks, and post-read re-stat;
  then implement stabilization with injected clock/sleeper/filesystem dependencies.
  Scenario: `A synchronizing file changes during read`.
- [x] 3.4 Add failing tests for maximum files, bytes, depth, duration, note size, and
  concurrency, plus per-directory error isolation and stable ordering/cursor behavior;
  then implement bounded scanning.
  Scenario: `Scan bounds are reached`.
- [x] 3.5 Add failing tests that ACA-managed export directories/metadata and embedded
  targets are ignored without opening referenced files; then implement loop guards.
  Scenarios: `ACA-generated export content is present`, `An embed references another
  vault file`.

## P4 — Unregistered Adapter Orchestration

Depends on: P1, P2, P3. Does not edit registry/OpenAPI/config union/MCP/fixture maps.

- [ ] 4.1 Add the `ContentSource.OBSIDIAN` storage-enum migration and adapter tests for
  a bounded scan mapping parsed authoritative Markdown to that source, exact
  persisted/skipped/failed counts, source outcomes, and bounded diagnostics; then
  implement the unregistered orchestrator.
  Scenario: `A configured vault scan completes durably`.
- [ ] 4.2 Add integration tests for unchanged, changed, renamed, deleted/reappearing,
  duplicate-URL, and different-annotation clips; then implement stable source identity
  and existing `canonical_id` linking while preserving each note body.
  Scenarios: `An unchanged file is observed again`, `A changed, renamed, or missing
  note is observed`, `Two distinct notes clip the same URL`.
- [ ] 4.3 Add two-worker and retry integration tests proving immutable event/content
  uniqueness under overlap and terminal-operation replay; then integrate transactional
  claims and reconciliation.
  Scenarios: `Two workers claim the same file version`, `A worker crashes around
  persistence`, `A caller forces replay`.
- [ ] 4.4 Add cancellation tests at enumeration, between candidates, before persistence,
  and while a claim is held; then implement cancellation checkpoints and claim release.
  Scenario: `A scan is cancelled`.
- [ ] 4.5 Add outcome/redaction tests for parse, encoding, path, size, stability, mount,
  and persistence failures across operation input/result, progress/events, logs, and
  RI-09 telemetry; then add safe diagnostic mapping.
  Scenarios: `A malformed note fails`, `The worker cannot access the configured mount`.
- [ ] 4.6 Add a dependency-boundary test proving ingress and
  `src/sync/obsidian_exporter.py` do not import one another and that successful/failed
  scans never mutate vault files.
  Scenarios: `A note succeeds or fails ingestion`, `ACA-generated export content is
  present`.

## P5 — Atomic Canonical Source Vertical

Depends on: P4. This package exclusively owns all shared hot files and MUST land as one
green commit.

- [ ] 5.1 Add failing contract tests for `ObsidianVaultIngestCommand` discriminator,
  public `source_key`/bounded scan options, forbidden path/note fields, and generated
  Python/TypeScript parity; update OpenAPI, regenerate bindings, and runtime re-exports.

  Scenarios: `Equivalent Obsidian submissions use one durable contract`, `Filesystem
  source capability is discovered`.
- [ ] 5.2 Add failing source-config tests for repeatable `ObsidianVaultSource`, stable
  `vault_id` natural key, private path/ingest-folder fields, database override round
  trip, safe management projection, HMAC public key, and allowed-root non-escalation;
  then extend the discriminated config union.
  Scenario: `Database override is projected safely`.
- [ ] 5.3 In the same package, add the `SOURCE_REGISTRY` descriptor, emitted
  `ContentSource.OBSIDIAN`, service/worker dispatch, configured-source snapshot
  enforcement, schedule metadata, and readiness resolver with completeness tests.

  Scenarios: `New source requires complete surface coverage`, `A configured vault scan
  completes durably`.
- [ ] 5.4 Add the hand-written MCP function, `INGESTION_TOOL_BY_SOURCE` mapping, exact
  toolset manifest, and CLI/HTTP/MCP contract tests proving the canonical command and
  equivalent `OperationHandle`/protocol-error behavior.
  Scenario: `Equivalent Obsidian submissions use one durable contract`.
- [ ] 5.5 Add capability-driven frontend tests for source discovery, generated fields,
  readiness/disabled display, submission, progress, terminal outcomes, and absence of
  private fields; change UI code only if registry projection is insufficient.
  Scenario: `Filesystem source capability is discovered`.
- [ ] 5.6 Add the exact deterministic `SOURCE_FIXTURES` entry and
  `LIVE_ADAPTER_POLICIES` entry in the same commit, including temporary-vault setup,
  network prohibition, missing-mount skip reason, and collection-time equality tests.

  Scenarios: `Obsidian fixture covers the canonical vertical`, `Obsidian registry
  entry is incomplete`, `Live Obsidian mount is unavailable`.
- [ ] 5.7 Run source workflow matrix, generated-contract drift, capability parity,
  worker dispatch, MCP manifest, frontend, and registry/fixture collection gates before
  committing the atomic vertical.

## P6 — End-to-End Reliability and Documentation

Depends on: P5.

- [ ] 6.1 Extend the offline real-ingestion tier with new/unchanged/changed/invalid/
  duplicate clips, database delta assertions, and no-network enforcement through
  `OperationService`.
  Scenarios: `Obsidian incremental ingestion matches durable evidence`, `Obsidian typed
  failure is retained`.
- [ ] 6.2 Add full durable retry, cancellation, idempotency, overlapping-session,
  migration, renderer-safety, and telemetry integration tests using isolated
  PostgreSQL sessions and temporary approved roots.
- [ ] 6.3 Add `sources.d/obsidian-vault.yaml.example` and setup/security/troubleshooting
  docs for local/co-located mounts, allowed roots, database overrides, sync-provider
  eventual consistency, bounds, privacy, and unavailable Railway/device-path cases.
- [ ] 6.4 Publish the strict Web Clipper template and compatibility matrix; explicitly
  document read-only behavior, required timezone-aware `captured_at`, required HTTP(S)
  URL, inert embeds, deferred features, and separation from knowledge-base export.
- [ ] 6.5 Run strict OpenSpec, workflow-contract drift, migration upgrade/downgrade,
  scoped format/lint/type checks, source workflow/fixture suites, durable operation
  regression suites, and security/redaction tests; record evidence and update roadmap
  checkpoint.

## Requirement Traceability

| Requirement | Implementation tasks |
|---|---|
| Worker-local bounded vault scan | 3.1, 3.4, 4.1, 4.4, 5.3, 6.1 |
| Strict clip contract | 1.1–1.3, 4.1, 6.4 |
| Race-safe filesystem containment | 3.1–3.5, 4.5, 6.2 |
| Deterministic Markdown normalization | 1.4, 4.1, 6.2 |
| Incremental state and concurrent claims | 2.1–2.5, 4.2–4.4, 6.1–6.2 |
| Canonical identity preserves note context | 1.5, 4.2–4.3, 5.3, 6.1 |
| Read-only ownership boundary | 3.5, 4.6, 6.3–6.4 |
| Private diagnostics and replay | 2.5, 4.3–4.5, 5.2–5.6, 6.1–6.2 |
| Registry-derived capability parity | 5.1–5.7 |
| Every registry entry maps to fixture/exclusion | 5.6–5.7, 6.1 |
| PR tier verifies durable database deltas | 6.1–6.2 |

## Dependency Graph

```text
P0
├── P1 parser/normalizer
├── P2 state/events/claims
└── P3 scanner/path policy
       \ | /
        P4 unregistered adapter
               |
        P5 atomic source vertical
               |
        P6 end-to-end/docs/gates
```

Maximum safe parallel width is three packages (P1/P2/P3). P5 is a mandatory
synchronization point because OpenAPI, generated bindings, configuration unions,
registry descriptors, MCP manifests, fixtures, live policy, and interface key sets must
remain collection-green together.
