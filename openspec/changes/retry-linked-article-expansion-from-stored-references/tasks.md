# Tasks: Retry linked-article expansion from stored references

> Change ID: `retry-linked-article-expansion-from-stored-references`

## 1. Storage

- [ ] 1.1 Migration: `expansion_state`, `expansion_attempts`, `expansion_attempted_at` on `content_references`, CHECKs, partial index, backfill of bookmark references to `pending`.
- [ ] 1.2 ORM columns on `ContentReference` and `ReferenceResponse`.

## 2. Recording and marking

- [ ] 2.1 References recorded for bookmark rows start `pending` (or `skipped` for feed/playlist links).
- [ ] 2.2 New-post expansion writes each link's outcome to every reference of its reference URL.

## 3. Retry

- [ ] 3.1 Retry pass on the leftover budget, oldest first, three-attempt limit, same skip rules, stop on first failure.
- [ ] 3.2 `retry_links` retry-only mode that skips the walk.

## 4. Contract and surfaces

- [ ] 4.1 `retry_links` in `XBookmarksIngestCommand` (canonical OpenAPI) and regenerated contracts.
- [ ] 4.2 Registry dispatch, orchestrator, MCP tool, and details sanitizer (`links_retried`, `links_pending`).

## 5. Tests and docs

- [ ] 5.1 Tests for every acceptance outcome, plus exact-shape tests updated for the new field.
- [ ] 5.2 docs/USER_GUIDE.md x-bookmarks section.
