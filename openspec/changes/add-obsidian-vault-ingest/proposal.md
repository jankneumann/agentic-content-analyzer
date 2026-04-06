# Change: Add Obsidian Vault Ingestion Bridge

## Why

The Obsidian Web Clipper already solves a hard UX problem for capture across desktop browsers, mobile browsers, and the Obsidian desktop app. Instead of building and maintaining separate capture clients, we can use Obsidian + a remote-synced vault as a lightweight capture bus into ACA ingestion.

This can simplify capture because:

1. **Capture surface is outsourced** to an existing mature tool (Obsidian Web Clipper)
2. **Cross-device behavior comes for free** via Obsidian Sync / iCloud / Dropbox / Git-backed vaults
3. **Ingestion becomes filesystem-first** (watch vault, process queue notes), reducing client API complexity
4. **Users keep ownership** of captured notes in plain markdown

## What Changes

### New Ingestion Mode: Vault Queue
- **NEW**: A configurable ingest source pointing to a vault subfolder, e.g. `Inbox/WebClipper/`
- **NEW**: Polling + optional filesystem watching for new/modified markdown notes
- **NEW**: Note-state tracking table (or metadata file) to ensure idempotent processing

### New Capture Contract
- **NEW**: Standard frontmatter contract for clipper-generated notes:
  - `source_url`
  - `captured_at`
  - `capture_client` (`obsidian-web-clipper`)
  - `content_type_hint` (`article|thread|video|paper|other`)
  - `ingest_status` (`queued|ingested|failed`) (managed by ACA)

### Markdown Normalization
- **NEW**: Normalizer for Obsidian-specific markdown patterns (wikilinks, embeds, callouts, attachments)
- **NEW**: Deterministic extraction of canonical URL and body content for the existing pipeline

### Sync Strategy
- **NEW**: Documented support matrix for remote storage backends:
  - Obsidian Sync
  - iCloud Drive
  - Dropbox / Google Drive
  - Git-based sync (advanced)
- **NEW**: Sync-safety rules (settling delay, lock-file handling, partial-write detection)

### Operational Controls
- **NEW**: Configuration knobs:
  - `OBSIDIAN_VAULT_PATH`
  - `OBSIDIAN_INGEST_FOLDER`
  - `OBSIDIAN_POLL_INTERVAL_SECONDS`
  - `OBSIDIAN_FILE_SETTLE_MS`
  - `OBSIDIAN_MOVE_PROCESSED_TO`
- **NEW**: Optional archive/move-after-ingest behavior to keep queue folders clean

## Pros / Cons

### Pros
- **Fast path to value**: little or no custom extension/app work
- **Cross-platform capture**: mobile + desktop + browser extension already available
- **Offline-first**: captures can happen offline and sync later
- **Open format**: markdown files are user-visible and portable
- **Reduced API exposure**: no public ingest endpoint required for capture clients

### Cons
- **Sync eventual consistency**: ingest may lag behind capture depending on provider
- **File race conditions**: partially synced files can cause parse errors without settle logic
- **Template drift risk**: clipper templates can vary across users and versions
- **Security/privacy surface**: local vault path and sync provider become part of threat model
- **Duplicate handling complexity**: same URL clipped multiple times with edits/annotations

## Specific Details to Consider

1. **Canonical identity strategy**
   - Deduplicate by canonicalized URL first, file hash second
   - Preserve note annotations as separate user commentary metadata

2. **Ingest trigger strategy**
   - Prefer poller for reliability across OS/providers
   - Optional FS notify watcher where supported; always keep poll fallback

3. **File settle and lock semantics**
   - Wait for stable mtime/size over settle window before parsing
   - Skip known temp/lock patterns from sync tools

4. **Template compatibility layer**
   - Provide ACA-recommended clipper template
   - Gracefully ingest notes missing optional fields

5. **Failure handling and replay**
   - Store parse failures with actionable reason
   - Reprocess notes when file changes or when manually retried

6. **Attachment handling**
   - Decide whether images/PDFs are in-scope for v1
   - If deferred, ignore gracefully and retain source links

7. **Security model**
   - Run least-privilege read-only on ingest folder when possible
   - Validate allowed vault roots to prevent path traversal

8. **User workflow ergonomics**
   - Optional post-ingest tagging in note frontmatter
   - Optional move note to `Processed/` folder

## Non-Goals (v1)

- Bi-directional sync back into Obsidian notes
- Full Obsidian plugin development
- Real-time collaborative conflict resolution
- Parsing every custom user template variant

## Impact

- **New spec**: `obsidian-vault-ingest`
- **Likely touched areas**:
  - ingestion source configuration
  - markdown parsing/normalization
  - job orchestration for filesystem queue
  - docs for setup and security guidance
- **No mandatory new external service** (reuses user-selected vault sync)

## Recommendation

Adopt Obsidian vault ingestion as a **capture ingress adapter**. Keep the core ACA pipeline unchanged by normalizing vault notes into the existing content ingestion contract.

This provides a pragmatic “build less, integrate more” path while preserving optional direct-capture APIs for non-Obsidian users.
