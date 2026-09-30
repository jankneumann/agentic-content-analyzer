# Retry linked-article expansion from stored references

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `retry-linked-article-expansion-from-stored-references`
> Effort: M
> Priority: 10

## Why

Linked-article expansion (ri-13) considers only the posts written in the
current run. A link whose submission failed, was cut by the per-run cap, or ran
outside the worker is never submitted again, because a rerun over known
bookmarks writes no posts. Every bookmark already records a `content_reference`
per link, so the retry list is in the database; it just has no state.

## What Changes

- `content_references` gains `expansion_state` (`pending`, `submitted`,
  `skipped`, `failed`; NULL for references from other sources),
  `expansion_attempts`, and `expansion_attempted_at`. Existing bookmark
  references are backfilled to `pending`.
- References recorded for bookmark rows start `pending`, or `skipped` for feed
  and playlist links that expansion never submits.
- Every expand-links run marks the references of the links it handled, then
  spends its leftover link budget on older `pending`/`failed` references,
  oldest first, up to three attempts per link.
- `XBookmarksIngestCommand.retry_links` (`aca ingest x-bookmarks --retry-links`,
  MCP `retry_links`): retry-only mode. It skips the timeline walk, needs no X
  session, and spends the full budget on the backlog.
- Envelope details `links_retried` and `links_pending`, both safe for durable
  results.

## Non-goals

- Tracking whether a submitted URL operation later succeeded; `submitted` is
  terminal here and the operation has its own retry policy.
- Retrying references from sources other than X bookmarks.

## Acceptance Outcomes

- References recorded for bookmark rows start pending (or skipped for feed and playlist links); references from other sources keep a NULL expansion state.
- A link whose submission failed or was capped is submitted by a later expand-links run from the leftover budget, oldest first.
- A link is not attempted after three failed submissions, and a link already stored as content is marked skipped instead of submitted.
- aca ingest x-bookmarks --retry-links submits pending links without fetching any bookmark page and needs no X session.
- A link shared by several bookmarks is submitted once and every one of its references records the outcome.
