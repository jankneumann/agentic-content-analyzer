# Tasks: Ingest X bookmarks incrementally as Content rows

> Change ID: `ingest-x-bookmarks-incrementally-as-content-rows`

## 1. Plan

- [x] 1.1 Read ri-10/ri-11/ri-16/ri-18 learnings, the client, xsearch, orchestrator, IngestionService
- [x] 1.2 Move the spec delta to `x-bookmarks-ingestion`
- [x] 1.3 Check for a per-source schedule mechanism (none; recorded in design.md)

## 2. Implement

- [x] 2.1 Share the xsearch renderer: optional `XThreadData.quoted`, `thread_title()`, `build_thread_metadata()`
- [x] 2.2 `bookmark_thread` / `bookmark_content_data`: `xpost:<id>`, links_json, metadata with `bookmarked: true`
- [x] 2.3 `XBookmarksIngestionService._walk`: known-page `stop_when`, `full`, `max_items`, dedup within a walk
- [x] 2.4 Fail closed on `CredentialFailureError`; warnings for `rate_limited` / `page_cap_reached` / `item_cap_reached`; `fetch_error` keeps what was read
- [x] 2.5 `_persist`: insert, cross-source flag, `force_reprocess` reset, per-row savepoints (no inline reference hook)
- [x] 2.6 `ingest_x_bookmarks`: resolve `expand_links` / `max_items` from the source, `ConfiguredSourceResult`
- [x] 2.7 Add the three warning codes to the sanitizer vocabulary, `WorkflowAlertDiagnosticCode`, and the alert envelope schema
- [x] 2.8 `iter_pages(start_cursor=)`; `SettingsBackfillCursorStore` (`x_bookmarks.backfill_cursor`); head walk then backfill; save/advance/clear; `full` resets
- [x] 2.9 Grok search `force_reprocess`: reset a same-`source_id` row of another source instead of inserting

## 3. Test

- [x] 3.1 Two-page walk ingests each bookmark once (including a post repeated across pages)
- [x] 3.2 Unchanged bookmarks: one page, zero rows; new bookmarks on top: only those; `full` walks all
- [x] 3.3 `max_items` cap and warning; page cap warning; `force_reprocess` reset in place
- [x] 3.4 Session expired (first and later page) and missing credentials: zero rows, no writes
- [x] 3.5 Rate limit mid-walk (partial + warning) and before the first page (error); upstream failure mid-walk
- [x] 3.6 Grok search row flagged, not duplicated; Grok search skips a bookmarked post
- [x] 3.7 Document shape through the shared renderer; Grok search output pinned
- [x] 3.8 Outbound links stored in `links_json` with no inline reference hook; filter hook runs from the orchestrator
- [x] 3.10 Backfill: capped first run saves the cursor; later runs ingest the next older batch; oldest clears it; head still stops on a known page; new bookmarks first; newer gap replaces the cursor; `full` resets; failed session leaves it; invalid stored values ignored; client start cursor
- [x] 3.11 Grok search `force_reprocess` resets a bookmark row instead of duplicating; alert-code parity test
- [x] 3.9 Durable path via `build_workflow_handler_registry` + real `IngestionService` (success and session expired)

## 4. Validate

- [x] 4.1 ruff 0.15.15 check/format, mypy on changed files
- [x] 4.2 pytest: new tests plus tests/ingestion, tests/test_ingestion, source workflow matrix, capability service, real_ingestion
- [x] 4.3 `openspec validate ingest-x-bookmarks-incrementally-as-content-rows --type change --strict`
