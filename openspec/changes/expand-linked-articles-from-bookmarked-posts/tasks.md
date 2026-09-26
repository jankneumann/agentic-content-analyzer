# Tasks: Expand linked articles from bookmarked posts

> Change ID: `expand-linked-articles-from-bookmarked-posts`

## 1. Plumbing

- [x] 1.1 `src/queue/follow_up_operations.py`: bind the worker loop and `OperationService`, submit from the ingestion thread, typed unavailable/timeout/deadlock errors
- [x] 1.2 Bind it around the ingestion `asyncio.to_thread` call in `src/queue/workflow_handlers.py`
- [x] 1.3 `ReferenceExtractor.store_references(..., commit=False)`
- [x] 1.4 Setting `x_bookmarks_max_expanded_links` (default 50)

## 2. X bookmarks

- [x] 2.1 Return the written rows from persistence; record one content_reference per article link in a savepoint
- [x] 2.2 `_expand_links`: skip self, media, non-http(s), feed/playlist and already-stored links; dedupe per run; cap; submit one url operation per link with a per-URL idempotency key, tags and note
- [x] 2.3 Warnings `link_expansion_capped`, `link_expansion_failed`, `persistence_error` (references); details counts

## 3. Contracts

- [x] 3.1 New codes in the result sanitizer, `WorkflowAlertDiagnosticCode`, and the alert envelope schema
- [x] 3.2 `references_recorded`, `links_submitted`, `links_skipped` in `SafeIngestionDetails`; regenerate contracts

## 4. Tests and validation

- [x] 4.1 expand on: one url operation and a reference; expand off: reference only
- [x] 4.2 Shared link submitted once; rerun submits nothing; stored link skipped
- [x] 4.3 Media, self, non-http, feed links never submitted
- [x] 4.4 Submission failure and missing worker warn and keep the rows; cap enforced; reference failure warns
- [x] 4.5 Durable handler path with the operations double; real `OperationService` against the test database
- [x] 4.6 Alert code parity contract test
- [x] 4.7 ruff 0.15.15, mypy, targeted pytest, `openspec validate --strict`
