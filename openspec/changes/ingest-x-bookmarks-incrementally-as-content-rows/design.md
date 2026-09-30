# Design: Ingest X bookmarks incrementally as Content rows

## Decisions

- **What "known" means.** A post is known when a row with its
  `xpost:<id>` exists as `x_bookmarks`, or any row with that `source_id`
  carries `metadata_json.bookmarked = true`. The lookup selects columns only,
  so it never registers as a touched row in the durable result's
  `content_ids`. The walk stops after the first page whose IDs are all known.
- **Fetch everything, then persist** (ri-05/ri-18 pattern). Credential
  failures on any page leave the database untouched. Rate limit, page cap, and
  upstream errors keep what was read because those pages are genuine
  bookmarks, and the gap below them is recorded as a backfill cursor (next
  decision). Credential failures write nothing, the cursor included.
- **Backfill cursor.** A head walk that stops on a known page would strand
  anything below a partial walk. The resume position is X's `cursor-bottom`
  token, kept in `settings_overrides` as `x_bookmarks.backfill_cursor` beside
  the client's query ID cache (fail-open the same way). A pass records: for an
  item cap that overflowed a page, the cursor that fetched that page (its taken
  posts are then known and skipped); for a cap at a page end, a page cap, a rate
  limit, or an upstream error, the cursor of the next request. A run walks the
  head first; when the head caught up and item/page budget remains, it walks
  from the saved cursor without stopping on known pages and saves the new
  position or clears it at the oldest bookmark. One slot is enough: a newer gap
  left by the head replaces the saved one, because a backfill from the newer
  gap walks down through the older one (re-reading known pages, bounded by the
  page budget and resumable). `full` ignores the cursor and resets it from its
  own outcome (only when it read a page). An overflow on the head's first page
  needs no cursor: the next head walk sees that page as not fully known.
- **`max_items` caps rows written**, counting only posts that will be written
  (new posts, plus known ones under `force_reprocess`). Reaching it before the
  walk caught up warns `item_cap_reached`; reaching it exactly at the end of
  the timeline does not.
- **Cross-source rows are flagged, never duplicated.** `contents` is unique on
  `(source_type, source_id)`, so a bookmark row beside a Grok search row would
  be legal. The adapter looks up the `source_id` across all types and flags the
  existing row instead. The flagged row counts as skipped
  (`details.linked_existing`), is not reprocessed, and is not passed to the
  reference hook (it was never rewritten).
- **Shared renderer, unchanged Grok search output.** `XPost` maps onto
  `XThreadData`; a quoted post gets an optional section that Grok search never
  sets. A test pins the Grok search content hash, title and metadata key order
  captured before the refactor.
- **No inline reference hook.** `on_content_ingested` is called by no adapter
  and enqueues a legacy `resolve_references` job via `asyncio.run`, which the
  canonical-workflow rule forbids restoring. Outbound links stay in
  `links_json`; ri-13 records `content_reference`s explicitly
  (`ReferenceExtractor.store_references`) and submits url operations through
  `OperationService`.
- **Status `pending`** on insert and on `force_reprocess`, matching Grok
  search rows.
- **Quiet hour: not added.** There is no per-source schedule:
  `settings/schedule.yaml` drives agent tasks, and scheduled ingestion runs
  every enabled source from the pipeline. The source stays disabled by default;
  an operator who wants a quiet-hour run can schedule
  `aca ingest x-bookmarks` separately (documentation is ri-17).

## Non-goals

- Link expansion and content_reference recording (ri-13), documentation
  (ri-17).

## Also fixed

- Grok search `force_reprocess` looked for an existing row of its own source
  type only, so it could insert an `xsearch` row beside a bookmark row with the
  same `xpost:<id>`. It now resets that row to `pending` in place (counted as
  ingested, like its own force updates) and never inserts a second row.
- The three walk codes join `WorkflowAlertDiagnosticCode` and the alert
  envelope schema enum together, so a failed run that carries `rate_limited`
  alerts with the code instead of a bare `operation_failed`.
