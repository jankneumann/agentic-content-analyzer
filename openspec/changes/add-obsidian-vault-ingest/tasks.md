# Implementation Tasks

## Dependency Graph Summary

- **Independent tracks**: 3 (A: config/state, B: parser/normalizer, C: docs/templates)
- **Sequential chains**: 4
- **Estimated max parallel width**: 3 tasks at once (after 1.1 + 2.1 complete)

## 1. Spec + Contract (Blocks most implementation)

- [ ] 1.1 Finalize Obsidian clip frontmatter contract (`source_url`, `captured_at`, optional fields)
- [ ] 1.2 Publish ACA-recommended Web Clipper template
- [ ] 1.3 Define compatibility behavior for missing/extra fields

## 2. Source Configuration + Validation (depends on 1.1)

- [ ] 2.1 Add settings for vault path + ingest folder + settle/poll controls
- [ ] 2.2 Enforce allowed-root validation and path traversal protection
- [ ] 2.3 Add runtime support for `type: obsidian_ingest` in source loader

## 3. Ingest State Schema (depends on 1.1)

- [ ] 3.1 Add migration for `obsidian_ingest_state` table
- [ ] 3.2 Add indexes for `status` and `canonical_url_hash`
- [ ] 3.3 Add data access methods for upsert/read transitions

## 4. Vault Queue Reader (depends on 2.1 + 3.1)

- [ ] 4.1 Implement poller for markdown files in ingest folder
- [ ] 4.2 Add file settle-window stabilization checks
- [ ] 4.3 Skip temp/lock/partial files safely
- [ ] 4.4 Add optional watcher trigger with poller fallback

## 5. Parser + Normalizer (depends on 1.1)

- [ ] 5.1 Parse frontmatter and validate required fields
- [ ] 5.2 Normalize Obsidian constructs (wikilinks/embeds/callouts)
- [ ] 5.3 Extract canonical URL + compute dedupe hashes
- [ ] 5.4 Map normalized payload to existing ingestion contract

## 6. Dedup + Replay Behavior (depends on 4.x + 5.x + 3.x)

- [ ] 6.1 Deduplicate by canonical URL hash (primary), file hash (fallback)
- [ ] 6.2 Record failure classes and actionable error messages
- [ ] 6.3 Auto-retry on file changes
- [ ] 6.4 Add manual reprocess operation for failed notes

## 7. Post-Ingest Actions (depends on 6.1)

- [ ] 7.1 Add optional move-to-processed-folder behavior
- [ ] 7.2 Handle filename collisions deterministically
- [ ] 7.3 Keep state-table idempotency when move is disabled

## 8. Tests (depends on 2–7, can run in parallel per suite)

- [ ] 8.1 Unit: frontmatter parsing, URL canonicalization, hash strategy
- [ ] 8.2 Integration: poller + settle behavior under partial-write simulation
- [ ] 8.3 Integration: duplicate clip replay and content linking behavior
- [ ] 8.4 Migration: `obsidian_ingest_state` create/rollback coverage
- [ ] 8.5 Negative-path: path traversal, malformed YAML, invalid URL

## 9. Documentation + Templates (track C, mostly independent)

- [ ] 9.1 Add setup docs for Obsidian Sync/iCloud/Dropbox variants
- [ ] 9.2 Add security/privacy and trust-boundary guidance
- [ ] 9.3 Add troubleshooting for sync lag, lock files, malformed clips
- [ ] 9.4 Maintain `sources.d/obsidian-ingest.yaml.example`
- [ ] 9.5 Promote to active `.yaml` only after 2.3 lands

## Requirement Traceability

- **R1 Vault Queue Ingestion** → 2.x, 4.x
- **R2 Frontmatter Contract** → 1.x, 5.x
- **R3 Sync-Safe File Handling** → 4.2, 4.3, 8.2
- **R4 Markdown Normalization** → 5.2, 5.4, 8.1
- **R5 Duplicate URL Behavior** → 5.3, 6.1, 8.3
- **R6 Failure Recording and Replay** → 6.2–6.4, 8.5
- **R7 Source Config Compatibility** → 2.3, 9.4, 9.5
- **R8 Path Safety** → 2.2, 8.5
