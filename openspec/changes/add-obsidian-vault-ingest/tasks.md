# Implementation Tasks

## 1. Spec + Contract

- [ ] 1.1 Define Obsidian clip note frontmatter contract and required fields
- [ ] 1.2 Document ACA-recommended Web Clipper template
- [ ] 1.3 Define compatibility behavior for missing/extra fields

## 2. Source Configuration

- [ ] 2.1 Add config for vault path + ingest folder
- [ ] 2.2 Add polling and settle-time config
- [ ] 2.3 Validate configured path is within allowed roots

## 3. Vault Queue Reader

- [ ] 3.1 Implement poller for markdown files in ingest folder
- [ ] 3.2 Add idempotent note-state tracking
- [ ] 3.3 Skip temp/lock/partial files safely

## 4. Markdown Normalization

- [ ] 4.1 Parse frontmatter and extract canonical URL
- [ ] 4.2 Normalize Obsidian markdown constructs to ingest-safe markdown
- [ ] 4.3 Map normalized payload to existing ingestion pipeline input

## 5. Error Handling + Replay

- [ ] 5.1 Persist parse/validation failures with reason
- [ ] 5.2 Auto-retry when note changes
- [ ] 5.3 Add manual reprocess command/path

## 6. Post-Ingest Actions

- [ ] 6.1 Add optional move-to-processed-folder behavior
- [ ] 6.2 Write `ingest_status` metadata updates without clobbering user edits

## 7. Tests

- [ ] 7.1 Unit tests for frontmatter parsing and URL canonicalization
- [ ] 7.2 Integration tests for poller + settle behavior
- [ ] 7.3 Regression tests for duplicate clips and replay semantics

## 8. Documentation

- [ ] 8.1 Setup guide for Obsidian Sync/iCloud/Dropbox variants
- [ ] 8.2 Security and privacy considerations
- [ ] 8.3 Troubleshooting guide for sync delays and malformed clips
