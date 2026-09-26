# Ingest X bookmarks incrementally as Content rows

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-12`)
> Change ID: `ingest-x-bookmarks-incrementally-as-content-rows`
> Effort: M · Priority: 1 · Depends on: `ri-10`, `ri-11`

## Why

The `x_bookmarks` source is registered (ri-10) and X's Bookmarks GraphQL
endpoint can be read from Python (ri-11), but `ingest_x_bookmarks` still fails
closed with `source_unavailable`: no bookmark reaches the corpus. The roadmap's
core outcome is that every post the operator bookmarks, on any device, lands
nightly as a Content row in the same document shape as the Grok search X
source, through the canonical durable workflow.

## What Changes

- New `src/ingestion/x_bookmarks.py` with `XBookmarksIngestionService`:
  - Walks `XBookmarksClient.iter_pages()` newest-first. `stop_when` ends the
    walk after the first page whose every post is already stored as a bookmark
    (an `x_bookmarks` row, or any row flagged `bookmarked`); `full=True`
    disables that. `max_items` caps the rows written.
  - Reads every page before writing. `CredentialsMissingError` /
    `SessionExpiredError` from any page => zero rows, `status=error`, code
    `credentials_missing` / `session_expired` (the durable result carries
    `command_key=x_bookmarks`, so ri-16's alert names `aca auth session x`).
    A walk X cut short (`rate_limited`, `page_cap`), capped by `max_items`, or
    failed upstream (`fetch_error`) persists what it read, warns
    (`rate_limited`, `page_cap_reached`, `item_cap_reached`), and saves where
    it stopped as the settings override `x_bookmarks.backfill_cursor`. A rate
    limit before the first page is an error.
  - Backfill: each run first walks the head (stopping on a known page); once
    caught up, with item/page budget left, it resumes from the saved cursor
    and advances it, or clears it on reaching the oldest bookmark. A newer gap
    left by the head replaces the saved cursor (a backfill from it walks down
    through everything older). `full=True` ignores the cursor and resets it
    from its own outcome. Credential failures leave the cursor untouched.
  - Each bookmark => one Content row: `source_type=x_bookmarks`,
    `source_id=xpost:<id>`, canonical `x.com` URL, Grok-search-style title and
    author, `published_date` = post time, markdown from the shared
    `format_thread_markdown`, `links_json` = outbound URLs (post, then quoted
    post), `metadata_json` = Grok search's X post keys plus author id,
    conversation/reply IDs, long-form flag, quoted post summary and
    `bookmarked: true`. Status `pending`, like Grok search rows.
  - Cross-source dedup: a post already stored under another source (Grok
    search) is not inserted again; that row gets `bookmarked: true` and counts
    as known from then on. Grok search already skips any existing
    `xpost:<id>` (level-1 check), so it never duplicates a bookmark.
  - `force_reprocess` rewrites and resets walked `x_bookmarks` rows to
    `pending` in place.
  - Outbound URLs are stored in `links_json`. No inline reference hook runs
    (no adapter uses one, and its legacy `resolve_references` enqueue is not a
    durable path); ri-13 records `content_reference`s explicitly.
  - `expand_links` is accepted, resolved, and passed to the point where ri-13
    hooks in; expansion itself is not implemented.
- `src/ingestion/orchestrator.py`: `ingest_x_bookmarks` (same keyword-only
  signature) resolves `expand_links=None` and `max_items=None` from the enabled
  source, runs the service, and adds one `ConfiguredSourceResult` for the
  configured source's public key. The module-level filter hook wraps it like
  every other `ingest_*` function.
- `src/ingestion/xsearch.py`: the renderer is shared without changing Grok
  search output: optional `XThreadData.quoted` (`XQuotedPost`) renders a
  `## Quoted Post` section only when set, `thread_title()` and
  `build_thread_metadata()` are factored out of `thread_to_content_data()` /
  `build_metadata()`.
  With `force_reprocess`, Grok search no longer inserts an `xsearch` row when
  another source already stores the same `xpost:<id>`: it resets that row to
  `pending` in place instead.
- `src/ingestion/x_bookmarks_client.py`: `iter_pages(start_cursor=)` resumes a
  walk from a saved `cursor-bottom` value.
- `src/ingestion/result_sanitizer.py`, `src/contracts/workflow_alert_models.py`
  and the workflow alert envelope schema
  (`openspec/changes/production-telemetry-and-out-of-band-alerting/contracts/workflow-alert-envelope.schema.json`):
  `rate_limited`, `page_cap_reached`, `item_cap_reached` join the closed
  diagnostic and alert code vocabularies together.
- `sources.d/x_bookmarks.yaml`: the `max_entries` comment describes the backfill.

## Impact

- Affected specs: `x-bookmarks-ingestion` (ADDED).
- Affected code: `src/ingestion/x_bookmarks.py` (new),
  `src/ingestion/x_bookmarks_client.py`, `src/ingestion/orchestrator.py`,
  `src/ingestion/xsearch.py`, `src/ingestion/result_sanitizer.py`,
  `src/contracts/workflow_alert_models.py`, the alert envelope schema.
- Tests: `tests/ingestion/test_x_bookmarks_ingestion.py` (new);
  `tests/ingestion/test_x_bookmarks_client.py` (start cursor);
  `tests/contract/test_workflow_alert_contracts.py` (walk-code parity);
  `tests/ingestion/test_x_bookmarks_registry.py` loses its two stub tests.
- New settings override key `x_bookmarks.backfill_cursor` (no migration).
- No migration, no contract change: `ContentSource.X_BOOKMARKS` and
  `XBookmarksIngestCommand` shipped with ri-09.
- The source still ships disabled (`sources.d/x_bookmarks.yaml`).
