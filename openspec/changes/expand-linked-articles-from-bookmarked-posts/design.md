# Design: Expand linked articles from bookmarked posts

## Decisions

- **Submit through the worker's own loop, not a private one.** The orchestrator
  runs in `asyncio.to_thread` and `OperationService.submit` is async; there is no
  synchronous submission path, and the legacy reference hook's
  `asyncio.run(enqueue_queue_job(...))` is what the canonical-workflow rule
  forbids. The ingestion handler therefore binds its running loop and
  `OperationService` in a context variable around the `to_thread` call; the
  thread hands each submit back with `run_coroutine_threadsafe` and waits (30 s
  timeout) until the row exists. No second loop, no loop-bound connection shared
  across loops, and tests inject the same operations double the handler uses.
  Submitting on the loop thread itself is refused (it would deadlock).
- **Not child operations.** The url operations are top-level, like an
  extension or `aca ingest url` submission. Parenting them to the ingestion
  operation would tie their lifecycle to a run that finishes first.
- **Idempotency.** `OperationService` deduplicates only active operations, so
  the key is per URL (`x_bookmarks.link:<sha256>`), not derived from the input
  (the note differs per bookmark). Across runs, rerun rows are known and not
  written, so they are not expanded; a URL already in `contents.source_url` (the
  webpage adapter's own dedup key) is skipped before submitting.
- **References commit with the row.** `store_references` gained
  `commit=False`; references go in a savepoint after the row's savepoint, so a
  reference failure drops only the references.
- **Stop at the first failed submission.** When the queue is unreachable every
  further submit would wait for its timeout; the rest are counted in
  `links_failed`.
- **Collections are referenced, not expanded.** Feed and YouTube playlist URLs
  would fan out into a whole feed or playlist through the url route.

## Non-goals

- Resolving the new references to the article rows (the existing
  `aca manage resolve-refs` batch does that once the url operation lands).
- Re-expanding links that were over the cap or failed in an earlier run.
- Documentation (ri-17).
