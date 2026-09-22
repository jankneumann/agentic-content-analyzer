# Ingest X bookmarks incrementally as Content rows

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `ingest-x-bookmarks-incrementally-as-content-rows`
> Effort: M
> Priority: 1

## Summary

Implement src/ingestion/x_bookmarks.py on top of the client with cursor pagination newest-first, persistence of each bookmark as a Content row with source_type=X_BOOKMARKS and source_id xpost:{id}, rendering through the same thread-to-markdown path as the Grok search adapter, and incremental sync that stops when an entire page's IDs already exist unless --full is passed.

## Dependencies

- `ri-10`
- `ri-11`

## Acceptance Outcomes

- A Hoverfly two-page cursor walk ingests every bookmark from both pages exactly once.
- A second run against unchanged bookmarks fetches exactly one page and ingests zero rows, and --full walks every page.
- A bookmarked post that Grok search later surfaces is deduplicated by source_id and not inserted twice.
- The ingestion filter hook and reference hook run on ingested bookmark rows like any other adapter.

## Rationale

Delivers the core proposal outcome that every bookmark lands in the corpus nightly through the canonical durable workflow, in the same document shape as the existing X source.
