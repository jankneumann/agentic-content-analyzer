# Tasks: Retry linked-article expansion from stored references

> Change ID: `retry-linked-article-expansion-from-stored-references`

## 1. Storage

- [x] 1.1 Migration: `expansion_state`, `expansion_attempts`, `expansion_attempted_at` on `content_references`, CHECKs, partial index, backfill of bookmark references to `pending`.
- [x] 1.2 ORM columns on `ContentReference` and `ReferenceResponse`.

## 2. Recording and marking

- [x] 2.1 References recorded for bookmark rows start `pending` (or `skipped` for feed/playlist links).
- [x] 2.2 New-post expansion writes each link's outcome to every reference of its reference URL.

## 3. Retry

- [x] 3.1 Retry pass on the leftover budget, oldest first, three-attempt limit, same skip rules, stop on first failure.
- [x] 3.2 `retry_links` retry-only mode that skips the walk.

## 4. Contract and surfaces

- [x] 4.1 `retry_links` in `XBookmarksIngestCommand` (canonical OpenAPI) and regenerated contracts.
- [x] 4.2 Registry dispatch, orchestrator, MCP tool, and details sanitizer (`links_retried`, `links_pending`).

## 5. Tests and docs

- [x] 5.1 Tests for every acceptance outcome, plus exact-shape tests updated for the new field.
- [x] 5.2 docs/USER_GUIDE.md x-bookmarks section.
