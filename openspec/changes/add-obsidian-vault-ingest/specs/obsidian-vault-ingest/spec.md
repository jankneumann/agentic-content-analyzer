# Obsidian Vault Ingest Capability

## ADDED Requirements

### Requirement: Worker-local bounded vault scan

The system SHALL ingest Obsidian clips only through one bounded canonical
`ingestion.execute` operation for a configured vault mounted on the executing worker.
The adapter MUST NOT start a long-lived poller, watcher, per-note child operation, or
parallel run-state model.

#### Scenario: A configured vault scan completes durably

- **GIVEN** an enabled Obsidian source whose ingest directory is mounted on the
  compatible worker
- **WHEN** its typed command is submitted
- **THEN** one `ingestion.execute` operation SHALL scan within configured hard bounds
- **AND** the terminal `OperationHandle` SHALL retain the canonical typed ingestion
  outcome and exact persisted, skipped, and failed counts

#### Scenario: The worker cannot access the configured mount

- **GIVEN** an Obsidian source whose private mount is absent, unreadable, or not routed
  to a compatible worker pool
- **WHEN** readiness is evaluated or a scan is submitted
- **THEN** the source SHALL fail closed with a stable `source_unavailable` diagnostic
- **AND** no vault path SHALL appear in the capability, error, operation, event, or log
  projection

#### Scenario: Scan bounds are reached

- **GIVEN** a vault exceeds the configured file, byte, recursion, duration, note-size,
  frontmatter-complexity, or concurrency ceiling
- **WHEN** a scan reaches that ceiling
- **THEN** the scan SHALL stop or defer additional candidates deterministically
- **AND** the operation outcome SHALL report bounded typed diagnostics without reading
  beyond the limit

#### Scenario: A scan is cancelled

- **GIVEN** a running Obsidian scan receives a cancellation request
- **WHEN** it reaches the next cancellation checkpoint between candidates or before
  persistence
- **THEN** processing SHALL stop without abandoning a permanent claim
- **AND** the operation SHALL use the standard cancelled lifecycle and domain outcome

### Requirement: Strict clip contract

The system SHALL parse bounded UTF-8 Markdown frontmatter using a safe YAML loader.
`source_url` MUST be an absolute bounded HTTP(S) URL without userinfo and
`captured_at` MUST be a timezone-aware RFC 3339 value. Optional `capture_client` and
`content_type_hint` values MUST follow the closed configured contract.

#### Scenario: Required metadata is valid

- **GIVEN** a stable note with valid `source_url` and timezone-aware `captured_at`
- **WHEN** the note is parsed
- **THEN** the URL and timestamp SHALL be mapped to provenance
- **AND** the frontmatter SHALL be removed from the authoritative Markdown body
- **AND** the source URL SHALL NOT be fetched

#### Scenario: Optional metadata is absent

- **GIVEN** a valid note without optional metadata
- **WHEN** the note is parsed
- **THEN** `capture_client` SHALL default to `obsidian-web-clipper`
- **AND** `content_type_hint` SHALL default to `other`

#### Scenario: Required metadata is missing or invalid

- **GIVEN** a note with missing metadata, a non-HTTP(S) or credential-bearing URL, or a
  missing-timezone timestamp
- **WHEN** the note is parsed
- **THEN** that note SHALL fail with `missing_required_metadata`, `invalid_url`, or
  `invalid_captured_at` as applicable
- **AND** filesystem mtime or file hash SHALL NOT substitute for the invalid field

#### Scenario: YAML exceeds the safe contract

- **GIVEN** YAML with custom tags, unsupported types, excessive bytes, nodes, depth,
  aliases, or bounded-string length
- **WHEN** the note is parsed
- **THEN** parsing SHALL stop with a stable bounded diagnostic
- **AND** no custom constructor or referenced content SHALL execute

### Requirement: Race-safe filesystem containment

The system SHALL enumerate and open regular files relative to a deployment-approved
root with no-follow semantics. It MUST reject absolute paths, NULs, traversal, every
symlink component, temporary files, ACA-generated export notes/folders, and any file
whose identity changes while being read.

#### Scenario: A path or symlink escapes containment

- **GIVEN** a leaf symlink, parent-directory symlink, absolute path, traversal path, or
  path component swapped after enumeration
- **WHEN** the scanner validates and opens the candidate
- **THEN** the candidate SHALL be rejected before its target bytes are consumed
- **AND** the diagnostic SHALL reveal neither target nor vault path

#### Scenario: A synchronizing file changes during read

- **GIVEN** a candidate whose descriptor identity, size, or timestamp changes across
  the settle/read/re-stat sequence
- **WHEN** the scanner evaluates stability
- **THEN** the note SHALL be deferred without parsing or persistence
- **AND** a later bounded scan MAY retry the new fingerprint

#### Scenario: An embed references another vault file

- **GIVEN** a note containing an Obsidian embed or attachment path
- **WHEN** normalization runs
- **THEN** the output SHALL contain only an inert readable placeholder
- **AND** the referenced file SHALL NOT be opened

### Requirement: Deterministic Markdown normalization

The system SHALL convert supported Obsidian Markdown constructs into deterministic
ingest-compatible Markdown while preserving unsupported input as inert readable text.

#### Scenario: Wikilinks and callouts are normalized

- **GIVEN** a note containing wikilinks and Obsidian callouts
- **WHEN** normalization runs
- **THEN** wikilinks SHALL become readable labels and callouts SHALL become blockquotes
- **AND** repeated normalization SHALL produce identical bytes

#### Scenario: Active-looking content remains inert

- **GIVEN** raw HTML, script-like text, `javascript:` or `data:` URI text, macros, or
  unsupported Obsidian syntax
- **WHEN** the note is normalized and displayed through any ACA renderer
- **THEN** no script, macro, URI, or attachment SHALL execute or dereference
- **AND** readable source text SHALL be preserved where safe

### Requirement: Incremental state and concurrent claims

The system SHALL key private state by the opaque configured-source digest and normalized
relative-path digest, and SHALL uniquely identify each file version by its content hash.
It SHALL use transactional compare-and-set or leased claims so overlapping scans,
retries, and crash recovery cannot persist the same version twice.

#### Scenario: An unchanged file is observed again

- **GIVEN** a completed state/event for a source, relative-path digest, and file hash
- **WHEN** another scan observes identical bytes
- **THEN** the candidate SHALL be skipped
- **AND** no duplicate content or ingest event SHALL be created

#### Scenario: Two workers claim the same file version

- **GIVEN** overlapping scans observe the same source, relative path, and file hash
- **WHEN** both attempt to claim it
- **THEN** exactly one claim SHALL own persistence
- **AND** the other scan SHALL skip or observe the completed event without duplicating
  content

#### Scenario: A worker crashes around persistence

- **GIVEN** a worker crashes before enqueue, after claim, after content persistence, or
  before state completion
- **WHEN** the lease expires or reconciliation runs
- **THEN** the state SHALL become retryable or reconcile to its existing content
- **AND** the immutable event identity SHALL prevent duplicate persistence

#### Scenario: A changed, renamed, or missing note is observed

- **GIVEN** an ingested note later changes bytes, moves to a new relative path, or is
  temporarily absent
- **WHEN** a later scan runs
- **THEN** changed bytes SHALL be eligible as a new version and a renamed path SHALL be
  a new note-level event
- **AND** absence SHALL NOT delete prior content

### Requirement: Canonical identity preserves note context

The system SHALL store clipped notes with `ContentSource.OBSIDIAN`. Canonicalized URL
identity SHALL link clips of the same page while each distinct note keeps its normalized
Markdown and annotations. File hash MUST NOT replace the required URL identity.

#### Scenario: Two distinct notes clip the same URL

- **GIVEN** two valid notes with the same canonical URL and different annotations
- **WHEN** both are ingested
- **THEN** each note's Markdown SHALL remain queryable as Obsidian content
- **AND** both SHALL link to one canonical primary through the existing canonical
  identity mechanism

#### Scenario: A URL contains tracking or sensitive query data

- **GIVEN** a valid clip URL with tracking parameters or a query string
- **WHEN** canonical identity and diagnostics are produced
- **THEN** configured tracking parameters SHALL be removed from canonical identity
- **AND** logs/results SHALL include at most the permitted origin or host, never the
  full URL, userinfo, or query

### Requirement: Read-only ownership boundary

Vault ingress SHALL be read-only and SHALL remain independent of Obsidian knowledge-base
export and sync code.

#### Scenario: A note succeeds or fails ingestion

- **GIVEN** any terminal note outcome
- **WHEN** processing completes
- **THEN** ACA SHALL NOT edit frontmatter, add tags, move, rename, or delete the note

#### Scenario: ACA-generated export content is present

- **GIVEN** a managed export directory or note marked with ACA exporter metadata exists
  beneath a scanned tree
- **WHEN** vault enumeration runs
- **THEN** that content SHALL be ignored to prevent an import/export loop
- **AND** ingress and export modules SHALL remain free of cross-imports

### Requirement: Private diagnostics and replay

The system SHALL expose only stable bounded error codes and opaque state/source
identifiers for note failures. Replay SHALL use the existing operation retry or the same
typed command with `force_reprocess`, never a caller-supplied path.

#### Scenario: A malformed note fails

- **GIVEN** a parse, encoding, path, size, or stability failure
- **WHEN** state, operation results, telemetry, or alerts record it
- **THEN** they SHALL omit absolute paths, relative names, full URLs, bodies,
  frontmatter, credentials, and raw exception messages
- **AND** a corrected file fingerprint SHALL be eligible for a later attempt

#### Scenario: A caller forces replay

- **GIVEN** an authorized caller submits the configured source with
  `force_reprocess=true` or retries its failed operation
- **WHEN** the command executes
- **THEN** the same path-safe bounded scan contract SHALL apply
- **AND** immutable event and content uniqueness SHALL still prevent duplicates
