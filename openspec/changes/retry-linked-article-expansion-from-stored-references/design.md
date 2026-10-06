# Design: Retry linked-article expansion from stored references

## Context

`_expand_links()` builds candidates from the outbound URLs of the posts written
in this run, drops links already stored as `Content.source_url`, and submits up
to `x_bookmarks_max_expanded_links` `UrlIngestCommand`s with the idempotency
key `x_bookmarks.link:<sha256(url)>`. The first submission failure stops the
run. Idempotency only collapses onto queued or running operations, so the same
key can be resubmitted after a failure.

References are written by `ReferenceExtractor.store_references()`. An arXiv,
DOI or S2 link becomes an identifier reference whose `external_url` is the
canonical URL, not the submitted one. `resolution_status` means "target content
found" and is only moved by the on-demand resolver, so it cannot double as the
expansion state.

## Decisions

### D1. New nullable state columns

`expansion_state VARCHAR(16) NULL` with a CHECK on the four values,
`expansion_attempts SMALLINT NOT NULL DEFAULT 0` (CHECK 0..100), and
`expansion_attempted_at TIMESTAMPTZ NULL`, plus a partial index on
`created_at WHERE expansion_state IN ('pending','failed')`. NULL means "not an
expansion candidate", so references from newsletters and other sources are
unaffected. The migration backfills references of `x_bookmarks` content rows
with an `external_url` to `pending`; the first retry pass marks the ones already
stored as `skipped`.

### D2. One outcome per URL, written to every reference of that URL

A link shared by several bookmarks is submitted once; the outcome is written to
all references whose `external_url` equals the link's reference URL (the
canonical URL for identifier references, computed with the same
`classify_reference_url` the recorder uses). New-post expansion keeps
submitting the URL it saw in the post, so existing behaviour and idempotency
keys are unchanged.

### D3. Retry pass uses the leftover budget

After new-post expansion, `budget = limit - submitted - failed attempts`. The
retry pass selects distinct reference URLs with state `pending` or `failed` and
fewer than three attempts, ordered by the oldest reference, skips the URLs the
run already handled, and applies the same skip rules (stored content, feed or
playlist, X self or media links). It stops at the first submission failure,
like the new-post loop. `submitted` and `skipped` are terminal. A link at three
failed attempts stays `failed` and is no longer selected.

### D4. Retry-only mode

`retry_links=True` returns before the timeline walk: no X request, no session
needed, no cursor movement, full budget on the backlog. The expansion is always
on in this mode, whatever the source's `expand_links`. Scheduled runs never set
it; they get the leftover-budget retry whenever `expand_links` is on.

### D5. Outcomes are reported as counts only

`links_retried` (submitted by the retry pass) and `links_pending` (backlog left
after the run) join the durable detail allowlist; no URL is reported.
