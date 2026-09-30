# Expand linked articles from bookmarked posts

> Parent roadmap: `x-bookmarks-session-capture` · Item `ri-13` · Effort S · Depends on `ri-12`

## Why

A bookmark on X is usually a receipt for an article. ri-12 stores each
bookmarked post as a Content row and keeps its outbound links in `links_json`,
but nothing records the post-to-article relationship and nothing ingests the
article itself, so the bookmark gesture captures the post and loses the reason
it was bookmarked.

## What Changes

- Every bookmark row written in a run (inserted, or rewritten under
  `force_reprocess`) gets one `content_reference` per distinct article link of
  the post and its quoted post, stored through
  `ReferenceExtractor.store_references` in the same transaction as the row and
  in its own savepoint. arXiv, DOI and Semantic Scholar links become identifier
  references; any other link is a URL-only reference (the partial-index path).
  This happens whether or not `expand_links` is on. No inline
  `on_content_ingested` hook and no legacy queue job are used.
- With `expand_links` resolved true, each distinct article link of the written
  rows that is not already stored as content is submitted as one canonical
  `url` ingestion operation (`UrlIngestCommand`, tags `["x-bookmark"]`, a note
  naming the post URL, auto routing) through `OperationService`, keyed
  `x_bookmarks.link:<sha256(url)>` so a shared or repeated link collapses onto a
  still-active operation. Rows that were only known or linked to a Grok search
  row are not expanded.
- Never submitted: X self links (x.com, twitter.com, t.co; also dropped by the
  client), X media hosts (`*.twimg.com`), non-http(s) links, and feed or YouTube
  playlist URLs (their url route would ingest a whole collection; they are still
  referenced).
- New setting `x_bookmarks_max_expanded_links` (default 50, 0 to 1000) bounds
  submissions per run; the overflow warns `link_expansion_capped`.
- A failed submission never fails the run: the rows and references are already
  in place, the rest of the links are not submitted, and the run warns
  `link_expansion_failed`. A reference write failure keeps the row and warns
  `persistence_error`.
- New `src/queue/follow_up_operations.py`: the canonical ingestion handler lends
  its event loop and `OperationService` to the ingestion thread (a context
  variable that `asyncio.to_thread` copies), and the thread submits with
  `run_coroutine_threadsafe`. Outside a worker handler submission fails with a
  typed error instead of running work inline.
- Durable result: `references_recorded`, `links_submitted`, `links_skipped`
  added to `SafeIngestionDetails` (additive contract change, regenerated);
  `link_expansion_capped` and `link_expansion_failed` added to the result
  sanitizer, `WorkflowAlertDiagnosticCode`, and the alert envelope schema.

## Impact

- Code: `src/ingestion/x_bookmarks.py`, `src/queue/follow_up_operations.py`
  (new), `src/queue/workflow_handlers.py`, `src/services/reference_extractor.py`
  (`store_references(..., commit=False)`), `src/config/settings.py`,
  `src/ingestion/result_sanitizer.py`, `src/contracts/workflow_alert_models.py`.
- Contracts: `openspec/contracts/content-workflows/openapi/v1.yaml` and its four
  generated outputs; `workflow-alert-envelope.schema.json`.
- Tests: `tests/ingestion/test_x_bookmarks_ingestion.py`,
  `tests/queue/test_follow_up_operations.py`,
  `tests/contract/test_workflow_alert_contracts.py`.
- Docs are owned by ri-17.
